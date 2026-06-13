import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    EntitlementNotFoundError,
    PlanNotFoundError,
    PricingNotFoundError,
)
from app.core.logging import get_logger
from app.models.plan import Plan, PlanEntitlement, PlanPricing

logger = get_logger(__name__)


async def get_plan_version(session: AsyncSession, plan_id: uuid.UUID, version: int) -> Plan:
    result = await session.execute(select(Plan).where(Plan.id == plan_id, Plan.version == version))
    plan = result.scalar_one_or_none()

    if plan is None:
        raise PlanNotFoundError(str(plan_id), version)

    return plan


async def get_latest_active_plan(session: AsyncSession, plan_id: uuid.UUID) -> Plan:
    result = await session.execute(
        select(Plan).where(Plan.id == plan_id, Plan.is_active == True)  # noqa: E712
    )
    plan = result.scalar_one_or_none()

    if plan is None:
        raise PlanNotFoundError(str(plan_id))

    return plan


async def list_all_plans(session: AsyncSession) -> list[Plan]:
    result = await session.execute(select(Plan))
    return list(result.scalars().all())


async def list_active_plans(session: AsyncSession) -> list[Plan]:
    result = await session.execute(
        select(Plan).where(Plan.is_active == True)  # noqa: E712
    )
    return list(result.scalars().all())


async def get_plan_pricing(
    session: AsyncSession, plan_id: uuid.UUID, version: int, currency: str
) -> PlanPricing:
    result = await session.execute(
        select(PlanPricing).where(
            PlanPricing.plan_id == plan_id,
            PlanPricing.plan_version == version,
            PlanPricing.currency == currency.upper(),
        )
    )
    pricing = result.scalar_one_or_none()

    if pricing is None:
        raise PricingNotFoundError(str(plan_id), version, currency)

    return pricing


async def get_plan_entitlements(
    session: AsyncSession, plan_id: uuid.UUID, version: int
) -> list[PlanEntitlement]:
    await get_plan_version(session, plan_id, version)

    result = await session.execute(
        select(PlanEntitlement).where(
            PlanEntitlement.plan_id == plan_id,
            PlanEntitlement.plan_version == version,
        )
    )
    return list(result.scalars().all())


async def get_plan_entitlement_by_key(
    session: AsyncSession, plan_id: uuid.UUID, version: int, feature_key: str
) -> PlanEntitlement:
    result = await session.execute(
        select(PlanEntitlement).where(
            PlanEntitlement.plan_id == plan_id,
            PlanEntitlement.plan_version == version,
            PlanEntitlement.feature_key == feature_key,
        )
    )
    entitlement = result.scalar_one_or_none()

    if entitlement is None:
        raise EntitlementNotFoundError(str(plan_id), version, feature_key)

    return entitlement


async def get_active_version_number(session: AsyncSession, plan_id: uuid.UUID) -> int | None:
    result = await session.execute(
        select(Plan.version).where(
            Plan.id == plan_id,
            Plan.is_active == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def deactivate_plan_version(session: AsyncSession, plan_id: uuid.UUID, version: int) -> None:
    await session.execute(
        update(Plan).where(Plan.id == plan_id, Plan.version == version).values(is_active=False)
    )
    logger.info("plan_version_deactivated", plan_id=str(plan_id), version=version)


async def insert_plan(session: AsyncSession, plan: Plan) -> None:
    session.add(plan)


async def insert_pricing_rows(session: AsyncSession, pricing_rows: list[PlanPricing]) -> None:
    session.add_all(pricing_rows)


async def insert_entitlement_rows(
    session: AsyncSession, entitlement_rows: list[PlanEntitlement]
) -> None:
    session.add_all(entitlement_rows)
