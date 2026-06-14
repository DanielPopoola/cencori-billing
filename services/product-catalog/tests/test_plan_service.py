"""
Service layer tests — verify business logic in isolation.

These tests call PlanService directly with a real DB session and a mocked
Redis client. They care about:
- Correct domain behaviour (versioning, pricing derivation, deactivation rules)
- Correct exceptions raised for invalid operations
- Correct data returned from service methods
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    DuplicatePlanNameError,
    PlanNotFoundError,
    PlanVersionAlreadyInactiveError,
    PricingNotFoundError,
)
from app.schemas.plans import (
    CreatePlanRequest,
    CreatePlanVersionRequest,
    CustomPricingResponse,
    PricingResponse,
)
from app.services.plan_service import PlanService
from tests.conftest import VALID_PLAN_BODY

pytestmark = pytest.mark.asyncio

ENTERPRISE_family_id = uuid.UUID("00000000-0000-0000-0000-000000000004")
PRO_family_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
FREE_family_id = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def plan_service(db_session: AsyncSession, mock_redis) -> PlanService:
    return PlanService(session=db_session, redis=mock_redis, settings=settings)


# ── create_plan ───────────────────────────────────────────────────────────────


async def test_create_plan_starts_at_version_1(plan_service: PlanService):
    request = CreatePlanRequest(**VALID_PLAN_BODY)
    result = await plan_service.create_plan(request)
    assert result.version == 1
    assert result.is_active is True


async def test_create_plan_lowercases_name(plan_service: PlanService):
    body = {**VALID_PLAN_BODY, "name": "STARTER"}
    request = CreatePlanRequest(**body)
    result = await plan_service.create_plan(request)
    assert result.name == "starter"


async def test_create_plan_raises_on_duplicate_name(plan_service: PlanService):
    body = {**VALID_PLAN_BODY, "name": "pro"}
    request = CreatePlanRequest(**body)
    with pytest.raises(DuplicatePlanNameError):
        await plan_service.create_plan(request)


async def test_create_plan_raises_on_duplicate_name_case_insensitive(
    plan_service: PlanService,
):
    body = {**VALID_PLAN_BODY, "name": "PRO"}
    request = CreatePlanRequest(**body)
    with pytest.raises(DuplicatePlanNameError):
        await plan_service.create_plan(request)


# ── create_plan_version ───────────────────────────────────────────────────────


async def test_create_plan_version_increments_version_number(plan_service: PlanService):
    # Create a base plan first
    base = await plan_service.create_plan(CreatePlanRequest(**VALID_PLAN_BODY))
    family_id = base.id

    version_body = {
        "pricing": [{"amount": 600000, "currency": "NGN"}],
        "entitlements": VALID_PLAN_BODY["entitlements"],
    }
    result = await plan_service.create_plan_version(family_id, CreatePlanVersionRequest(**version_body))
    assert result.version == 2


async def test_create_plan_version_deactivates_previous(plan_service: PlanService):
    base = await plan_service.create_plan(CreatePlanRequest(**VALID_PLAN_BODY))
    family_id = base.id

    version_body = {
        "pricing": [{"amount": 600000, "currency": "NGN"}],
        "entitlements": VALID_PLAN_BODY["entitlements"],
    }
    await plan_service.create_plan_version(family_id, CreatePlanVersionRequest(**version_body))

    v1 = await plan_service.get_plan_version(family_id, 1)
    assert v1.is_active is False


async def test_create_plan_version_new_version_is_active(plan_service: PlanService):
    base = await plan_service.create_plan(CreatePlanRequest(**VALID_PLAN_BODY))
    family_id = base.id

    version_body = {
        "pricing": [{"amount": 600000, "currency": "NGN"}],
        "entitlements": VALID_PLAN_BODY["entitlements"],
    }
    v2 = await plan_service.create_plan_version(family_id, CreatePlanVersionRequest(**version_body))
    assert v2.is_active is True


# ── deactivate_plan ───────────────────────────────────────────────────────────


async def test_deactivate_plan_sets_is_active_false(plan_service: PlanService):
    base = await plan_service.create_plan(CreatePlanRequest(**VALID_PLAN_BODY))
    result = await plan_service.deactivate_plan(base.id, 1)
    assert result.is_active is False


async def test_deactivate_plan_raises_if_already_inactive(plan_service: PlanService):
    base = await plan_service.create_plan(CreatePlanRequest(**VALID_PLAN_BODY))
    await plan_service.deactivate_plan(base.id, 1)

    with pytest.raises(PlanVersionAlreadyInactiveError):
        await plan_service.deactivate_plan(base.id, 1)


async def test_deactivate_plan_raises_for_unknown_plan(plan_service: PlanService):
    with pytest.raises(PlanNotFoundError):
        await plan_service.deactivate_plan(uuid.uuid4(), 1)


# ── get_pricing ───────────────────────────────────────────────────────────────


async def test_get_pricing_derives_correct_annual_amount(plan_service: PlanService):
    result = await plan_service.get_pricing(PRO_family_id, 1, "NGN")
    assert isinstance(result, PricingResponse)
    expected = int(3_900_000 * 12 * (1 - settings.ANNUAL_DISCOUNT_RATE))
    assert result.annual_amount == expected


async def test_get_pricing_returns_custom_pricing_for_enterprise(
    plan_service: PlanService,
):
    result = await plan_service.get_pricing(ENTERPRISE_family_id, 1, "NGN")
    assert isinstance(result, CustomPricingResponse)
    assert result.is_custom_pricing is True


async def test_get_pricing_raises_for_unknown_currency(plan_service: PlanService):
    with pytest.raises(PricingNotFoundError):
        await plan_service.get_pricing(PRO_family_id, 1, "JPY")


# ── get_plan_version ──────────────────────────────────────────────────────────


async def test_get_plan_version_returns_correct_plan(plan_service: PlanService):
    result = await plan_service.get_plan_version(PRO_family_id, 1)
    assert result.name == "pro"
    assert result.version == 1


async def test_get_plan_version_raises_for_unknown_version(plan_service: PlanService):
    with pytest.raises(PlanNotFoundError):
        await plan_service.get_plan_version(PRO_family_id, 99)


# ── get_latest_plan ───────────────────────────────────────────────────────────


async def test_get_latest_plan_returns_active_version(plan_service: PlanService):
    result = await plan_service.get_latest_plan(PRO_family_id)
    assert result.is_active is True
    assert result.name == "pro"


async def test_get_latest_plan_returns_newest_after_versioning(
    plan_service: PlanService,
):
    base = await plan_service.create_plan(CreatePlanRequest(**VALID_PLAN_BODY))
    family_id = base.id

    version_body = {
        "pricing": [{"amount": 600000, "currency": "NGN"}],
        "entitlements": VALID_PLAN_BODY["entitlements"],
    }
    await plan_service.create_plan_version(family_id, CreatePlanVersionRequest(**version_body))

    latest = await plan_service.get_latest_plan(family_id)
    assert latest.version == 2


# ── get_entitlements ──────────────────────────────────────────────────────────


async def test_get_entitlements_returns_all_feature_keys(plan_service: PlanService):
    result = await plan_service.get_entitlements(FREE_family_id, 1)
    keys = [e.feature_key for e in result.entitlements]
    assert "request_quota" in keys
    assert "security_scanning" in keys


async def test_get_entitlement_by_key_returns_correct_value(plan_service: PlanService):
    result = await plan_service.get_entitlement_by_key(PRO_family_id, 1, "request_quota")
    assert result.feature_key == "request_quota"
    assert result.value.type == "numeric"
    assert result.value.limit == 50000


async def test_free_plan_security_scanning_is_disabled(plan_service: PlanService):
    result = await plan_service.get_entitlement_by_key(FREE_family_id, 1, "security_scanning")
    assert result.value.enabled is False


async def test_pro_plan_security_scanning_is_enabled(plan_service: PlanService):
    result = await plan_service.get_entitlement_by_key(PRO_family_id, 1, "security_scanning")
    assert result.value.enabled is True
