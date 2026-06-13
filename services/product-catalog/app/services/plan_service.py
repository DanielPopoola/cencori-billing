from __future__ import annotations

import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import DuplicatePlanNameError, PlanVersionAlreadyInactiveError
from app.core.logging import get_logger
from app.models.plan import Plan, PlanEntitlement, PlanPricing, ProductCatalogOutbox
from app.repositories.cache import redis_cache as cache
from app.repositories.db import plan as repo
from app.schemas.plans import (
    CreatePlanRequest,
    CreatePlanVersionRequest,
    CustomPricingResponse,
    DeactivatedPlanResponse,
    EntitlementEntry,
    EntitlementResponse,
    EntitlementsResponse,
    PlanVersionResponse,
    PricingEntry,
    PricingResponse,
)

logger = get_logger(__name__)


class PlanService:
    def __init__(self, session: AsyncSession, redis: aioredis.Redis, settings: Settings) -> None:
        self._session = session
        self._redis = redis
        self._settings = settings

    @property
    def settings(self) -> Settings:
        return self._settings

    async def get_plan_version(self, plan_id: uuid.UUID, version: int) -> PlanVersionResponse:
        cached = await cache.get_cached_plan(self._redis, plan_id, version)
        if cached:
            return cached

        plan = await repo.get_plan_version(self._session, plan_id, version)
        response = self._to_plan_response(plan)
        await cache.cache_plan(self._redis, plan_id, version, response)
        return response

    async def get_latest_plan(self, plan_id: uuid.UUID) -> PlanVersionResponse:
        cached_version = await cache.get_cached_latest_version(self._redis, plan_id)
        if cached_version is not None:
            cached = await cache.get_cached_plan(self._redis, plan_id, cached_version)
            if cached:
                return cached

        plan = await repo.get_latest_active_plan(self._session, plan_id)
        response = self._to_plan_response(plan)
        await cache.cache_plan(self._redis, plan.id, plan.version, response)
        await cache.cache_latest_pointer(self._redis, plan.id, plan.version)
        return response

    async def list_plans(self) -> list[PlanVersionResponse]:
        plans = await repo.list_active_plans(self._session)
        return [self._to_plan_response(p) for p in plans]

    async def get_pricing(
        self, plan_id: uuid.UUID, version: int, currency: str
    ) -> PricingResponse | CustomPricingResponse:
        plan = await repo.get_plan_version(self._session, plan_id, version)

        if plan.is_custom_pricing:
            return CustomPricingResponse(
                plan_id=plan.id,
                plan_name=plan.name,
                plan_version=plan.version,
            )

        pricing = await repo.get_plan_pricing(self._session, plan_id, version, currency)
        annual_amount = self._derive_annual_amount(pricing.amount)

        return PricingResponse(
            plan_id=plan.id,
            plan_name=plan.name,
            plan_version=plan.version,
            currency=pricing.currency,
            monthly_amount=pricing.amount,
            annual_amount=annual_amount,
            annual_discount_rate=self._settings.annual_discount_rate,
        )

    async def get_entitlements(self, plan_id: uuid.UUID, version: int) -> EntitlementsResponse:
        entitlements = await repo.get_plan_entitlements(self._session, plan_id, version)
        return EntitlementsResponse(
            plan_id=plan_id,
            plan_version=version,
            entitlements=[
                EntitlementEntry(feature_key=e.feature_key, value=e.value) for e in entitlements
            ],
        )

    async def get_entitlement_by_key(
        self, plan_id: uuid.UUID, version: int, feature_key: str
    ) -> EntitlementResponse:
        entitlement = await repo.get_plan_entitlement_by_key(
            self._session, plan_id, version, feature_key
        )
        return EntitlementResponse(
            plan_id=plan_id,
            plan_version=version,
            feature_key=entitlement.feature_key,
            value=entitlement.value,
        )

    async def create_plan(self, request: CreatePlanRequest) -> PlanVersionResponse:
        await self._assert_plan_name_is_unique(request.name)

        plan_id = uuid.uuid4()
        plan = Plan(id=plan_id, name=request.name.lower(), version=1)
        pricing_rows = self._build_pricing_rows(plan_id, version=1, pricing=request.pricing)
        entitlement_rows = self._build_entitlement_rows(
            plan_id, version=1, entitlements=request.entitlements
        )
        outbox_event = self._build_created_event(plan, previous_version=None)

        await repo.insert_plan(self._session, plan)
        await repo.insert_pricing_rows(self._session, pricing_rows)
        await repo.insert_entitlement_rows(self._session, entitlement_rows)
        self._session.add(outbox_event)

        await self._session.flush()
        await self._session.refresh(plan)

        response = self._to_plan_response(plan)
        await cache.update_cache_after_write(self._redis, plan, response)

        logger.info("plan_created", plan_id=str(plan_id), name=plan.name)
        return response

    async def create_plan_version(
        self, plan_id: uuid.UUID, request: CreatePlanVersionRequest
    ) -> PlanVersionResponse:
        previous_version = await repo.get_active_version_number(self._session, plan_id)
        # Fetch the plan name from the previous version for the outbox event
        existing = await repo.get_plan_version(self._session, plan_id, previous_version)
        new_version = previous_version + 1

        plan = Plan(id=plan_id, name=existing.name, version=new_version)
        pricing_rows = self._build_pricing_rows(plan_id, new_version, request.pricing)
        entitlement_rows = self._build_entitlement_rows(plan_id, new_version, request.entitlements)
        created_event = self._build_created_event(plan, previous_version=previous_version)
        deactivated_event = self._build_deactivated_event(
            plan_id=plan_id,
            plan_name=existing.name,
            version=previous_version,
            reason=f"superseded_by_version_{new_version}",
        )

        await repo.deactivate_plan_version(self._session, plan_id, previous_version)
        await repo.insert_plan(self._session, plan)
        await repo.insert_pricing_rows(self._session, pricing_rows)
        await repo.insert_entitlement_rows(self._session, entitlement_rows)

        self._session.add(created_event)
        self._session.add(deactivated_event)

        await self._session.flush()
        await self._session.refresh(plan)

        response = self._to_plan_response(plan)
        await cache.update_cache_after_write(self._redis, plan, response)

        logger.info(
            "plan_version_created",
            plan_id=str(plan_id),
            version=new_version,
            previous_version=previous_version,
        )
        return response

    async def deactivate_plan(self, plan_id: uuid.UUID, version: int) -> DeactivatedPlanResponse:
        plan = await repo.get_plan_version(self._session, plan_id, version)

        if not plan.is_active:
            raise PlanVersionAlreadyInactiveError(str(plan_id), version)

        outbox_event = self._build_deactivated_event(
            plan_id=plan_id,
            plan_name=plan.name,
            version=version,
            reason="manual_deactivation",
        )

        await repo.deactivate_plan_version(self._session, plan_id, version)
        self._session.add(outbox_event)

        await self._session.flush()
        await self._session.refresh(plan)

        await cache.invalidate_cache_after_deactivation(self._redis, plan_id, version)

        logger.info("plan_manually_deactivated", plan_id=str(plan_id), version=version)
        return DeactivatedPlanResponse(
            id=plan_id,
            name=plan.name,
            version=version,
            is_active=False,
            deactivated_at=datetime.now(UTC),
        )

    def _derive_annual_amount(self, monthly_amount: int) -> int:
        return int(monthly_amount * 12 * (1 - self._settings.ANNUAL_DISCOUNT_RATE))

    def _build_pricing_rows(
        self, plan_id: uuid.UUID, version: int, pricing: list[PricingEntry]
    ) -> list[PlanPricing]:
        return [
            PlanPricing(
                plan_id=plan_id,
                plan_version=version,
                amount=p.amount,
                currency=p.currency,
            )
            for p in pricing
        ]

    def _build_entitlement_rows(
        self, plan_id: uuid.UUID, version: int, entitlements: list[EntitlementEntry]
    ) -> list[PlanEntitlement]:
        return [
            PlanEntitlement(
                plan_id=plan_id,
                plan_version=version,
                feature_key=e.feature_key,
                value=e.value.model_dump(),
            )
            for e in entitlements
        ]

    def _build_created_event(self, plan: Plan, previous_version: int | None) -> ProductCatalogOutbox:
        return ProductCatalogOutbox(
            event_type="plan.version.created",
            payload={
                "event_id": str(uuid.uuid4()),
                "event_type": "plan.version.created",
                "timestamp": datetime.now(UTC).isoformat(),
                "payload": {
                    "plan_id": str(plan.id),
                    "plan_name": plan.name,
                    "version": plan.version,
                    "previous_version": previous_version,
                    "is_active": True,
                    "is_custom_pricing": plan.is_custom_pricing,
                    "pricing": [{"amount": p.amount, "currency": p.currency} for p in plan.pricing],
                    "entitlements": [
                        {"feature_key": e.feature_key, "value": e.value} for e in plan.entitlements
                    ],
                },
            },
        )

    def _build_deactivated_event(
        self, plan_id: uuid.UUID, plan_name: str, version: int, reason: str
    ) -> ProductCatalogOutbox:
        return ProductCatalogOutbox(
            event_type="plan.version.deactivated",
            payload={
                "event_id": str(uuid.uuid4()),
                "event_type": "plan.version.deactivated",
                "timestamp": datetime.now(UTC).isoformat(),
                "payload": {
                    "plan_id": str(plan_id),
                    "plan_name": plan_name,
                    "version": version,
                    "reason": reason,
                },
            },
        )

    def _to_plan_response(self, plan: Plan) -> PlanVersionResponse:
        return PlanVersionResponse(
            id=plan.id,
            name=plan.name,
            version=plan.version,
            is_active=plan.is_active,
            is_custom_pricing=plan.is_custom_pricing,
            pricing=[PricingEntry(amount=p.amount, currency=p.currency) for p in plan.pricing],
            entitlements=[
                EntitlementEntry(feature_key=e.feature_key, value=e.value) for e in plan.entitlements
            ],
            created_at=plan.created_at,
        )

    async def _assert_plan_name_is_unique(self, name: str) -> None:
        plans = await repo.list_all_plans(self._session)
        existing_names = {p.name.lower() for p in plans}
        if name.lower() in existing_names:
            raise DuplicatePlanNameError(name)
