from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import JSONResponse

from app.core.exceptions import UnauthorizedError
from app.core.response import success
from app.schemas.plans import (
    CreatePlanRequest,
    CreatePlanVersionRequest,
    CustomPricingResponse,
    DeactivatedPlanResponse,
    EntitlementResponse,
    EntitlementsResponse,
    PlanVersionResponse,
    PricingResponse,
)
from app.services.dependencies import get_plan_service
from app.services.plan_service import PlanService

router = APIRouter(prefix="/plans", tags=["plans"])


def require_admin_token(
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
    service: PlanService = Depends(get_plan_service),
) -> None:
    if x_admin_token != service.settings.ADMIN_TOKEN:
        raise UnauthorizedError()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PlanVersionResponse)
async def create_plan(
    body: CreatePlanRequest,
    service: PlanService = Depends(get_plan_service),
    _: None = Depends(require_admin_token),
) -> JSONResponse:
    plan = await service.create_plan(body)
    return success(data=plan, status_code=status.HTTP_201_CREATED)


@router.post(
    "/{plan_id}/versions", status_code=status.HTTP_201_CREATED, response_model=PlanVersionResponse
)
async def create_plan_version(
    plan_id: uuid.UUID,
    body: CreatePlanVersionRequest,
    service: PlanService = Depends(get_plan_service),
    _: None = Depends(require_admin_token),
) -> JSONResponse:
    plan = await service.create_plan_version(plan_id, body)
    return success(data=plan, status_code=status.HTTP_201_CREATED)


@router.patch("/{plan_id}/versions/{version}/deactivate", response_model=DeactivatedPlanResponse)
async def deactivate_plan_version(
    plan_id: uuid.UUID,
    version: int,
    service: PlanService = Depends(get_plan_service),
    _: None = Depends(require_admin_token),
) -> JSONResponse:
    result = await service.deactivate_plan(plan_id, version)
    return success(data=result)


@router.get("")
async def list_plans(
    service: PlanService = Depends(get_plan_service),
) -> JSONResponse:
    plans = await service.list_plans()
    return success(data=plans)


@router.get("/{plan_id}/versions/latest", response_model=list[PlanVersionResponse])
async def get_latest_plan(
    plan_id: uuid.UUID,
    service: PlanService = Depends(get_plan_service),
) -> JSONResponse:
    plan = await service.get_latest_plan(plan_id)
    return success(data=plan)


@router.get("/{plan_id}/versions/{version}", response_model=PlanVersionResponse)
async def get_plan_version(
    plan_id: uuid.UUID,
    version: int,
    service: PlanService = Depends(get_plan_service),
) -> JSONResponse:
    plan = await service.get_plan_version(plan_id, version)
    return success(data=plan)


@router.get(
    "/{plan_id}/versions/{version}/pricing", response_model=PricingResponse | CustomPricingResponse
)
async def get_plan_pricing(
    plan_id: uuid.UUID,
    version: int,
    currency: str = Query(..., min_length=3, max_length=3),
    service: PlanService = Depends(get_plan_service),
) -> JSONResponse:
    pricing = await service.get_pricing(plan_id, version, currency)
    return success(data=pricing)


@router.get("/{plan_id}/versions/{version}/entitlements", response_model=EntitlementsResponse)
async def get_plan_entitlements(
    plan_id: uuid.UUID,
    version: int,
    service: PlanService = Depends(get_plan_service),
) -> JSONResponse:
    entitlements = await service.get_entitlements(plan_id, version)
    return success(data=entitlements)


@router.get(
    "/{plan_id}/versions/{version}/entitlements/{feature_key}", response_model=EntitlementResponse
)
async def get_plan_entitlement_by_key(
    plan_id: uuid.UUID,
    version: int,
    feature_key: str,
    service: PlanService = Depends(get_plan_service),
) -> JSONResponse:
    entitlement = await service.get_entitlement_by_key(plan_id, version, feature_key)
    return success(data=entitlement)
