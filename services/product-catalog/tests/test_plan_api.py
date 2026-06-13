"""
Route tests — verify the HTTP contract.

These tests care about:
- Correct status codes
- Correct response envelope shape (success/error)
- Auth enforcement on write endpoints
- Validation rejection on bad input

They do NOT test business logic in detail — that's the service layer's job.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import ADMIN_HEADERS, VALID_PLAN_BODY

pytestmark = pytest.mark.asyncio

# Known seeded plan ID (from seed.sql)
PRO_PLAN_ID = "00000000-0000-0000-0000-000000000002"
FREE_PLAN_ID = "00000000-0000-0000-0000-000000000001"
ENTERPRISE_PLAN_ID = "00000000-0000-0000-0000-000000000004"


# ── GET /api/v1/plans ─────────────────────────────────────────────────────────

async def test_list_plans_returns_200(client: AsyncClient):
    response = await client.get("/api/v1/plans")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)


async def test_list_plans_includes_seeded_plans(client: AsyncClient):
    response = await client.get("/api/v1/plans")
    names = [p["name"] for p in response.json()["data"]]
    assert "free" in names
    assert "pro" in names
    assert "team" in names


# ── GET /api/v1/plans/:id/versions/latest ─────────────────────────────────────

async def test_get_latest_plan_returns_200(client: AsyncClient):
    response = await client.get(f"/api/v1/plans/{PRO_PLAN_ID}/versions/latest")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["name"] == "pro"
    assert body["data"]["version"] == 1
    assert body["data"]["is_active"] is True


async def test_get_latest_plan_returns_404_for_unknown_plan(client: AsyncClient):
    response = await client.get(
        "/api/v1/plans/00000000-0000-0000-0000-999999999999/versions/latest"
    )
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "plan_not_found"


# ── GET /api/v1/plans/:id/versions/:version ───────────────────────────────────

async def test_get_plan_version_returns_200(client: AsyncClient):
    response = await client.get(f"/api/v1/plans/{PRO_PLAN_ID}/versions/1")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["id"] == PRO_PLAN_ID
    assert body["data"]["version"] == 1


async def test_get_plan_version_returns_404_for_nonexistent_version(client: AsyncClient):
    response = await client.get(f"/api/v1/plans/{PRO_PLAN_ID}/versions/99")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "plan_not_found"


# ── GET /api/v1/plans/:id/versions/:version/pricing ──────────────────────────

async def test_get_pricing_returns_monthly_and_annual_amounts(client: AsyncClient):
    response = await client.get(
        f"/api/v1/plans/{PRO_PLAN_ID}/versions/1/pricing?currency=NGN"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["monthly_amount"] == 3900000
    assert data["annual_amount"] > 0
    assert data["annual_discount_rate"] == 0.17


async def test_get_pricing_returns_custom_pricing_for_enterprise(client: AsyncClient):
    response = await client.get(
        f"/api/v1/plans/{ENTERPRISE_PLAN_ID}/versions/1/pricing?currency=NGN"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["is_custom_pricing"] is True
    assert "message" in data


async def test_get_pricing_returns_404_for_unknown_currency(client: AsyncClient):
    response = await client.get(
        f"/api/v1/plans/{PRO_PLAN_ID}/versions/1/pricing?currency=JPY"
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "pricing_not_found"


async def test_get_pricing_rejects_invalid_currency(client: AsyncClient):
    response = await client.get(
        f"/api/v1/plans/{PRO_PLAN_ID}/versions/1/pricing?currency=XX"
    )
    assert response.status_code == 422


# ── GET /api/v1/plans/:id/versions/:version/entitlements ─────────────────────

async def test_get_entitlements_returns_all_features(client: AsyncClient):
    response = await client.get(f"/api/v1/plans/{PRO_PLAN_ID}/versions/1/entitlements")
    assert response.status_code == 200
    entitlements = response.json()["data"]["entitlements"]
    keys = [e["feature_key"] for e in entitlements]
    assert "request_quota" in keys
    assert "security_scanning" in keys


async def test_get_entitlement_by_key_returns_correct_value(client: AsyncClient):
    response = await client.get(
        f"/api/v1/plans/{PRO_PLAN_ID}/versions/1/entitlements/request_quota"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["feature_key"] == "request_quota"
    assert data["value"]["type"] == "numeric"
    assert data["value"]["limit"] == 50000


async def test_get_entitlement_by_key_returns_404_for_unknown_key(client: AsyncClient):
    response = await client.get(
        f"/api/v1/plans/{PRO_PLAN_ID}/versions/1/entitlements/nonexistent_feature"
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "entitlement_not_found"


# ── POST /api/v1/plans ────────────────────────────────────────────────────────

async def test_create_plan_returns_201(client: AsyncClient):
    response = await client.post(
        "/api/v1/plans", json=VALID_PLAN_BODY, headers=ADMIN_HEADERS
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "starter"
    assert data["version"] == 1
    assert data["is_active"] is True


async def test_create_plan_requires_admin_token(client: AsyncClient):
    response = await client.post("/api/v1/plans", json=VALID_PLAN_BODY)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_create_plan_rejects_wrong_admin_token(client: AsyncClient):
    response = await client.post(
        "/api/v1/plans", json=VALID_PLAN_BODY, headers={"X-Admin-Token": "wrong"}
    )
    assert response.status_code == 401


async def test_create_plan_rejects_duplicate_name(client: AsyncClient):
    body = {**VALID_PLAN_BODY, "name": "pro"}
    response = await client.post("/api/v1/plans", json=body, headers=ADMIN_HEADERS)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "duplicate_plan_name"


async def test_create_plan_rejects_invalid_currency(client: AsyncClient):
    body = {
        **VALID_PLAN_BODY,
        "pricing": [{"amount": 1000, "currency": "XYZ"}],
    }
    response = await client.post("/api/v1/plans", json=body, headers=ADMIN_HEADERS)
    assert response.status_code == 422


async def test_create_plan_rejects_negative_amount(client: AsyncClient):
    body = {
        **VALID_PLAN_BODY,
        "pricing": [{"amount": -1, "currency": "NGN"}],
    }
    response = await client.post("/api/v1/plans", json=body, headers=ADMIN_HEADERS)
    assert response.status_code == 422


async def test_create_plan_rejects_invalid_entitlement_shape(client: AsyncClient):
    body = {
        **VALID_PLAN_BODY,
        "entitlements": [
            # numeric value missing "limit"
            {"feature_key": "request_quota", "value": {"type": "numeric"}}
        ],
    }
    response = await client.post("/api/v1/plans", json=body, headers=ADMIN_HEADERS)
    assert response.status_code == 422


# ── POST /api/v1/plans/:id/versions ──────────────────────────────────────────

async def test_create_plan_version_increments_version(client: AsyncClient):
    # First create a new plan to version
    create_response = await client.post(
        "/api/v1/plans", json=VALID_PLAN_BODY, headers=ADMIN_HEADERS
    )
    plan_id = create_response.json()["data"]["id"]

    version_body = {
        "pricing": [{"amount": 600000, "currency": "NGN"}],
        "entitlements": VALID_PLAN_BODY["entitlements"],
    }
    response = await client.post(
        f"/api/v1/plans/{plan_id}/versions",
        json=version_body,
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 201
    assert response.json()["data"]["version"] == 2


async def test_create_plan_version_deactivates_previous_version(client: AsyncClient):
    create_response = await client.post(
        "/api/v1/plans", json=VALID_PLAN_BODY, headers=ADMIN_HEADERS
    )
    plan_id = create_response.json()["data"]["id"]

    version_body = {
        "pricing": [{"amount": 600000, "currency": "NGN"}],
        "entitlements": VALID_PLAN_BODY["entitlements"],
    }
    await client.post(
        f"/api/v1/plans/{plan_id}/versions",
        json=version_body,
        headers=ADMIN_HEADERS,
    )

    v1_response = await client.get(f"/api/v1/plans/{plan_id}/versions/1")
    assert v1_response.json()["data"]["is_active"] is False


# ── PATCH /api/v1/plans/:id/versions/:version/deactivate ─────────────────────

async def test_deactivate_plan_returns_200(client: AsyncClient):
    create_response = await client.post(
        "/api/v1/plans", json=VALID_PLAN_BODY, headers=ADMIN_HEADERS
    )
    plan_id = create_response.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/plans/{plan_id}/versions/1/deactivate",
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is False


async def test_deactivate_plan_returns_409_if_already_inactive(client: AsyncClient):
    create_response = await client.post(
        "/api/v1/plans", json=VALID_PLAN_BODY, headers=ADMIN_HEADERS
    )
    plan_id = create_response.json()["data"]["id"]

    await client.patch(
        f"/api/v1/plans/{plan_id}/versions/1/deactivate", headers=ADMIN_HEADERS
    )
    # Second deactivation
    response = await client.patch(
        f"/api/v1/plans/{plan_id}/versions/1/deactivate", headers=ADMIN_HEADERS
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "plan_version_already_inactive"


async def test_deactivate_plan_returns_404_for_unknown_plan(client: AsyncClient):
    response = await client.patch(
        "/api/v1/plans/00000000-0000-0000-0000-999999999999/versions/1/deactivate",
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 404