"""
Seed script for plans, plan_pricing, and plan_entitlements.
Uses SQLAlchemy ORM models. Requires DATABASE_URL in environment or .env file.
"""

import asyncio
import os
import uuid

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.plan import Plan, PlanEntitlement, PlanFamily, PlanPricing

load_dotenv()

PLANS = [
    {
        "id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
        "name": "free",
        "version": 1,
        "is_active": True,
        "is_custom_pricing": False,
        "pricing": {"amount": 0, "currency": "NGN"},
        "entitlements": {
            "request_quota": {"type": "numeric", "limit": 1000},
            "active_projects": {"type": "numeric", "limit": 1},
            "security_scanning": {"type": "boolean", "enabled": False},
            "jailbreak_detection": {"type": "boolean", "enabled": False},
            "pii_masking": {"type": "boolean", "enabled": False},
            "caching": {"type": "boolean", "enabled": False},
            "observability": {"type": "boolean", "enabled": False},
        },
    },
    {
        "id": uuid.UUID("00000000-0000-0000-0000-000000000002"),
        "name": "pro",
        "version": 1,
        "is_active": True,
        "is_custom_pricing": False,
        "pricing": {"amount": 3_900_000, "currency": "NGN"},
        "entitlements": {
            "request_quota": {"type": "numeric", "limit": 50_000},
            "active_projects": {"type": "numeric", "limit": -1},
            "security_scanning": {"type": "boolean", "enabled": True},
            "jailbreak_detection": {"type": "boolean", "enabled": True},
            "pii_masking": {"type": "boolean", "enabled": True},
            "caching": {"type": "boolean", "enabled": True},
            "observability": {"type": "boolean", "enabled": True},
        },
    },
    {
        "id": uuid.UUID("00000000-0000-0000-0000-000000000003"),
        "name": "team",
        "version": 1,
        "is_active": True,
        "is_custom_pricing": False,
        "pricing": {"amount": 15_000_000, "currency": "NGN"},
        "entitlements": {
            "request_quota": {"type": "numeric", "limit": 250_000},
            "active_projects": {"type": "numeric", "limit": -1},
            "security_scanning": {"type": "boolean", "enabled": True},
            "jailbreak_detection": {"type": "boolean", "enabled": True},
            "pii_masking": {"type": "boolean", "enabled": True},
            "caching": {"type": "boolean", "enabled": True},
            "observability": {"type": "boolean", "enabled": True},
            "team_seats": {"type": "boolean", "enabled": True},
            "end_user_billing": {"type": "boolean", "enabled": True},
        },
    },
    {
        "id": uuid.UUID("00000000-0000-0000-0000-000000000004"),
        "name": "enterprise",
        "version": 1,
        "is_active": True,
        "is_custom_pricing": True,
        "pricing": None,
        "entitlements": {
            "request_quota": {"type": "numeric", "limit": -1},
            "active_projects": {"type": "numeric", "limit": -1},
            "security_scanning": {"type": "boolean", "enabled": True},
            "jailbreak_detection": {"type": "boolean", "enabled": True},
            "pii_masking": {"type": "boolean", "enabled": True},
            "caching": {"type": "boolean", "enabled": True},
            "observability": {"type": "boolean", "enabled": True},
            "team_seats": {"type": "boolean", "enabled": True},
            "end_user_billing": {"type": "boolean", "enabled": True},
            "custom_sla": {"type": "boolean", "enabled": True},
        },
    },
]


async def seed(session: AsyncSession) -> None:
    for data in PLANS:
        # Skip if plan already exists (ON CONFLICT DO NOTHING equivalent)
        existing = await session.get(PlanFamily, data["id"])
        if existing:
            print(f"- Skipping plan: {data['name']} (already exists)")
            continue

        plan_family = PlanFamily(
            id=data["id"], name=data["name"], is_custom_pricing=data["is_custom_pricing"]
        )
        session.add(plan_family)

        plan = Plan(
            id=uuid.uuid4(),
            family_id=data["id"],
            version=data["version"],
            is_active=data["is_active"],
        )
        session.add(plan)

        if data["pricing"]:
            session.add(
                PlanPricing(
                    family_id=data["id"],
                    plan_version=data["version"],
                    amount=data["pricing"]["amount"],
                    currency=data["pricing"]["currency"],
                )
            )

        for feature_key, value in data["entitlements"].items():
            session.add(
                PlanEntitlement(
                    family_id=data["id"],
                    plan_version=data["version"],
                    feature_key=feature_key,
                    value=value,
                )
            )

        print(f"✓ Seeded plan: {data['name']}")

    await session.commit()


async def main() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        await seed(session)

    await engine.dispose()
    print("\nAll plans seeded successfully.")


if __name__ == "__main__":
    asyncio.run(main())
