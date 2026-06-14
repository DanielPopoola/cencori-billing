"""
Shared test fixtures.

Stack:
- testcontainers spins up a real PostgreSQL container per test session
- Migrations are run from the SQL files in migrations/product_catalog/
- Seed data is loaded from services/product-catalog/seed/seed.sql
- Each test gets a clean AsyncClient pointed at the real app
- Redis is mocked — we test business logic, not cache internals

Fixture scopes:
- postgres_url: session — one container for the whole test run
- db_engine:    session — one engine per test run
- db_session:   function — fresh transaction per test, rolled back after
- client:       function — fresh AsyncClient per test
"""

from __future__ import annotations

import os
import asyncio
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer
from unittest.mock import AsyncMock, MagicMock


from app.core.database import Base
from app.seed.seed import seed

# Paths
REPO_ROOT = Path(__file__).parent.parent.parent.parent  # cencori-billing/
MIGRATIONS_DIR = REPO_ROOT / "migrations" / "product_catalog"
SEED_FILE = REPO_ROOT / "services" / "product-catalog" / "seed" / "seed.sql"

ADMIN_TOKEN = "test-admin-token"


# ── PostgreSQL container ──────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def postgres_url():
    """Spin up a real PostgreSQL container for the test session."""
    with PostgresContainer("postgres:18-alpine") as pg:
        yield pg.get_connection_url().replace("psycopg2", "asyncpg")


@pytest_asyncio.fixture(scope="session")
async def db_engine(postgres_url: str):
    """Create the async engine and run all migrations + seed once per session."""
    engine = create_async_engine(postgres_url, poolclass=NullPool)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await seed(session)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a session wrapped in a transaction that rolls back after each test.
    This keeps tests isolated without re-seeding between every test.
    """
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


# ── Redis mock ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_redis():
    """
    Mock Redis client. Cache behaviour is tested indirectly via service tests.
    All cache calls succeed silently — we're testing business logic, not Redis.
    """
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=True)
    redis.sadd = AsyncMock(return_value=True)
    redis.srem = AsyncMock(return_value=True)
    return redis


# ── App client ────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, mock_redis) -> AsyncGenerator[AsyncClient, None]:
    """
    AsyncClient wired to the real app with DB and Redis overridden.
    Admin token is set to a known test value via environment.
    """
    os.environ["ADMIN_TOKEN"] = ADMIN_TOKEN
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost/test"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "localhost:9092"

    from app.core.config import settings

    settings.ADMIN_TOKEN = ADMIN_TOKEN

    from app.core.cache import get_redis
    from app.core.database import get_session
    from app.main import app

    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: mock_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop


# ── Helpers ───────────────────────────────────────────────────────────────────

VALID_PLAN_BODY = {
    "name": "starter",
    "pricing": [{"amount": 500000, "currency": "NGN"}],
    "entitlements": [
        {"feature_key": "request_quota", "value": {"type": "numeric", "limit": 5000}},
        {"feature_key": "security_scanning", "value": {"type": "boolean", "enabled": False}},
    ],
}

ADMIN_HEADERS = {"X-Admin-Token": ADMIN_TOKEN}
