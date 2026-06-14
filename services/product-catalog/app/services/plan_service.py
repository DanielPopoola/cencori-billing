"""
Plan service — orchestrates all plan business logic.

Owns the transaction boundary for writes. The repository never commits.
The router never touches the session directly.

After the plan_families restructure:
- family_id in all public methods refers to the family ID (stable identifier)
- plan.family gives access to name, is_custom_pricing
- plan.family.pricing and plan.family.entitlements give related rows
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import DuplicatePlanNameError, PlanVersionAlreadyInactiveError
from app.core.logging import get_logger
from app.models.plan import Plan, PlanEntitlement, PlanFamily, PlanPricing, ProductCatalogOutbox
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
    """
    Orchestrates plan reads, writes, and cache management.
    One instance per request — injected via FastAPI dependency.
    """

    def __init__(
        self,
        session: AsyncSession,
        redis: aioredis.Redis,
        settings: Settings,
    ) -> None:
        self._session = session
        self._redis = redis
        self._settings = settings

    @property
    def settings(self) -> Settings:
        return self._settings

    # ── Read operations ───────────────────────────────────────────────────────
    async def get_plan_version(self, family_id: uuid.UUID, version: int) -> PlanVersionResponse:
        cached = await cache.get_cached_plan(self._redis, family_id, version)
        if cached:
            return cached

        plan = await repo.get_plan_version(self._session, family_id, version)
        response = self._to_plan_response(plan)
        await cache.cache_plan(self._redis, family_id, version, response)
        return response

    async def get_latest_plan(self, family_id: uuid.UUID) -> PlanVersionResponse:
        cached_version = await cache.get_cached_latest_version(self._redis, family_id)
        if cached_version is not None:
            cached = await cache.get_cached_plan(self._redis, family_id, cached_version)
            if cached:
                return cached

        plan = await repo.get_latest_active_plan(self._session, family_id)
        response = self._to_plan_response(plan)
        await cache.cache_plan(self._redis, family_id, plan.version, response)
        await cache.cache_latest_pointer(self._redis, family_id, plan.version)
        return response

    async def list_plans(self) -> list[PlanVersionResponse]:
        plans = await repo.list_all_plans(self._session)
        return [self._to_plan_response(p) for p in plans]

    async def get_pricing(
        self, family_id: uuid.UUID, version: int, currency: str
    ) -> PricingResponse | CustomPricingResponse:
        plan = await repo.get_plan_version(self._session, family_id, version)

        if plan.family.is_custom_pricing:
            return CustomPricingResponse(
                family_id=family_id,
                plan_name=plan.family.name,
                plan_version=plan.version,
            )

        pricing = await repo.get_plan_pricing(self._session, family_id, version, currency)
        return PricingResponse(
            family_id=family_id,
            plan_name=plan.family.name,
            plan_version=plan.version,
            currency=pricing.currency,
            monthly_amount=pricing.amount,
            annual_amount=self._derive_annual_amount(pricing.amount),
            annual_discount_rate=self._settings.ANNUAL_DISCOUNT_RATE,
        )

    async def get_entitlements(self, family_id: uuid.UUID, version: int) -> EntitlementsResponse:
        entitlements = await repo.get_plan_entitlements(self._session, family_id, version)
        return EntitlementsResponse(
            family_id=family_id,
            plan_version=version,
            entitlements=[
                EntitlementEntry(feature_key=e.feature_key, value=e.value) for e in entitlements
            ],
        )

    async def get_entitlement_by_key(
        self, family_id: uuid.UUID, version: int, feature_key: str
    ) -> EntitlementResponse:
        entitlement = await repo.get_plan_entitlement_by_key(
            self._session, family_id, version, feature_key
        )
        return EntitlementResponse(
            family_id=family_id,
            plan_version=version,
            feature_key=entitlement.feature_key,
            value=entitlement.value,
        )

    # ── Write operations ──────────────────────────────────────────────────────

    async def create_plan(self, request: CreatePlanRequest) -> PlanVersionResponse:
        await self._assert_plan_name_is_unique(request.name)

        family_id = uuid.uuid4()
        family = PlanFamily(
            id=family_id,
            name=request.name.lower(),
            is_custom_pricing=False,
        )
        plan = Plan(id=uuid.uuid4(), family_id=family_id, version=1)
        pricing_rows = self._build_pricing_rows(family_id, version=1, pricing=request.pricing)
        entitlement_rows = self._build_entitlement_rows(
            family_id, version=1, entitlements=request.entitlements
        )

        self._session.add(family)
        self._session.add(plan)
        self._session.add_all(pricing_rows)
        self._session.add_all(entitlement_rows)
        await self._session.flush()
        await self._session.refresh(plan)
        await self._session.refresh(family)

        outbox_event = self._build_created_event(
            family_id=family_id,
            family_name=family.name,
            version=1,
            previous_version=None,
            is_custom_pricing=family.is_custom_pricing,
            pricing=pricing_rows,
            entitlements=entitlement_rows,
        )
        self._session.add(outbox_event)
        await self._session.flush()

        response = self._to_plan_response(plan)
        await cache.update_cache_after_write(self._redis, family_id, plan.version, response)

        logger.info("plan_created", family_id=str(family_id), name=family.name)
        return response

    async def create_plan_version(
        self, family_id: uuid.UUID, request: CreatePlanVersionRequest
    ) -> PlanVersionResponse:
        previous_version = await repo.get_active_version_number(self._session, family_id)
        if previous_version:
            existing = await repo.get_plan_version(self._session, family_id, previous_version)
            new_version = previous_version + 1

            plan = Plan(id=uuid.uuid4(), family_id=family_id, version=new_version)
            pricing_rows = self._build_pricing_rows(family_id, new_version, request.pricing)
            entitlement_rows = self._build_entitlement_rows(family_id, new_version, request.entitlements)

            await repo.deactivate_plan_version(self._session, family_id, previous_version)
            self._session.add(plan)
            self._session.add_all(pricing_rows)
            self._session.add_all(entitlement_rows)
            await self._session.flush()
            await self._session.refresh(plan)

            created_event = self._build_created_event(
                family_id=family_id,
                family_name=existing.family.name,
                version=new_version,
                previous_version=previous_version,
                is_custom_pricing=existing.family.is_custom_pricing,
                pricing=pricing_rows,
                entitlements=entitlement_rows,
            )
            deactivated_event = self._build_deactivated_event(
                family_id=family_id,
                family_name=existing.family.name,
                version=previous_version,
                reason=f"superseded_by_version_{new_version}",
            )
            self._session.add(created_event)
            self._session.add(deactivated_event)
            await self._session.flush()

            response = self._to_plan_response(plan)
            await cache.update_cache_after_write(self._redis, family_id, new_version, response)
            await cache.invalidate_cache_after_deactivation(self._redis, family_id, previous_version)

            logger.info(
                "plan_version_created",
                family_id=str(family_id),
                version=new_version,
                previous_version=previous_version,
            )
            return response

    async def deactivate_plan(self, family_id: uuid.UUID, version: int) -> DeactivatedPlanResponse:
        plan = await repo.get_plan_version(self._session, family_id, version)

        if not plan.is_active:
            raise PlanVersionAlreadyInactiveError(str(family_id), version)

        family_name = plan.family.name
        deactivated_event = self._build_deactivated_event(
            family_id=family_id,
            family_name=family_name,
            version=version,
            reason="manual_deactivation",
        )

        await repo.deactivate_plan_version(self._session, family_id, version)
        self._session.add(deactivated_event)
        await self._session.flush()

        await cache.invalidate_cache_after_deactivation(self._redis, family_id, version)

        logger.info("plan_manually_deactivated", family_id=str(family_id), version=version)
        return DeactivatedPlanResponse(
            id=family_id,
            name=family_name,
            version=version,
            is_active=False,
            deactivated_at=datetime.now(UTC),
        )

    def _derive_annual_amount(self, monthly_amount: int) -> int:
        return int(monthly_amount * 12 * (1 - self._settings.ANNUAL_DISCOUNT_RATE))

    def _build_pricing_rows(
        self, family_id: uuid.UUID, version: int, pricing: list[PricingEntry]
    ) -> list[PlanPricing]:
        return [
            PlanPricing(family_id=family_id, plan_version=version, amount=p.amount, currency=p.currency)
            for p in pricing
        ]

    def _build_entitlement_rows(
        self, family_id: uuid.UUID, version: int, entitlements: list[EntitlementEntry]
    ) -> list[PlanEntitlement]:
        return [
            PlanEntitlement(
                family_id=family_id,
                plan_version=version,
                feature_key=e.feature_key,
                value=e.value.model_dump(),
            )
            for e in entitlements
        ]

    def _build_created_event(
        self,
        family_id: uuid.UUID,
        family_name: str,
        version: int,
        previous_version: int | None,
        is_custom_pricing: bool,
        pricing: list[PlanPricing],
        entitlements: list[PlanEntitlement],
    ) -> ProductCatalogOutbox:
        return ProductCatalogOutbox(
            event_type="plan.version.created",
            payload={
                "event_id": str(uuid.uuid4()),
                "event_type": "plan.version.created",
                "timestamp": datetime.now(UTC).isoformat(),
                "payload": {
                    "family_id": str(family_id),
                    "plan_name": family_name,
                    "version": version,
                    "previous_version": previous_version,
                    "is_active": True,
                    "is_custom_pricing": is_custom_pricing,
                    "pricing": [{"amount": p.amount, "currency": p.currency} for p in pricing],
                    "entitlements": [
                        {"feature_key": e.feature_key, "value": e.value} for e in entitlements
                    ],
                },
            },
        )

    def _build_deactivated_event(
        self, family_id: uuid.UUID, family_name: str, version: int, reason: str
    ) -> ProductCatalogOutbox:
        return ProductCatalogOutbox(
            event_type="plan.version.deactivated",
            payload={
                "event_id": str(uuid.uuid4()),
                "event_type": "plan.version.deactivated",
                "timestamp": datetime.now(UTC).isoformat(),
                "payload": {
                    "family_id": str(family_id),
                    "plan_name": family_name,
                    "version": version,
                    "reason": reason,
                },
            },
        )

    def _to_plan_response(self, plan: Plan) -> PlanVersionResponse:
        return PlanVersionResponse(
            id=plan.family_id,
            name=plan.family.name,
            version=plan.version,
            is_active=plan.is_active,
            is_custom_pricing=plan.family.is_custom_pricing,
            pricing=[
                PricingEntry(amount=p.amount, currency=p.currency)
                for p in plan.family.pricing
                if p.plan_version == plan.version
            ],
            entitlements=[
                EntitlementEntry(feature_key=e.feature_key, value=e.value)
                for e in plan.family.entitlements
                if e.plan_version == plan.version
            ],
            created_at=plan.created_at,
        )

    # ── Validation helpers ────────────────────────────────────────────────────

    async def _assert_plan_name_is_unique(self, name: str) -> None:
        families = await repo.list_all_families(self._session)
        existing_names = {f.name.lower() for f in families}
        if name.lower() in existing_names:
            raise DuplicatePlanNameError(name)
