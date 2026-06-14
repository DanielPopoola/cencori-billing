import uuid

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.plans import PlanVersionResponse

logger = get_logger(__name__)


def _version_key(family_id: uuid.UUID, version: int) -> str:
    return f"plan:{family_id}:v:{version}"


def _latest_key(family_id: uuid.UUID) -> str:
    return f"plan:{family_id}:latest"


_ACTIVE_PLANS_KEY = "plans:active"


async def get_cached_plan(
    redis: aioredis.Redis, family_id: uuid.UUID, version: int
) -> PlanVersionResponse | None:
    try:
        raw = await redis.get(_version_key(family_id, version))
        if raw:
            return PlanVersionResponse.model_validate_json(raw)
    except Exception:
        logger.warning("cache_read_failed", family_id=str(family_id), version=version)
    return None


async def get_cached_latest_version(redis: aioredis.Redis, family_id: uuid.UUID) -> int | None:
    try:
        raw = await redis.get(_latest_key(family_id))
        return int(raw) if raw else None
    except Exception:
        logger.warning("cache_latest_read_failed", family_id=str(family_id))
    return None


async def cache_plan(
    redis: aioredis.Redis, family_id: uuid.UUID, version: int, response: PlanVersionResponse
) -> None:
    try:
        await redis.setex(
            _version_key(family_id, version),
            settings.CACHE_TTL_SECONDS,
            response.model_dump_json(),
        )
    except Exception:
        # Cache failure is non-fatal — PostgreSQL remains the fallback
        logger.warning("cache_write_failed", family_id=str(family_id), version=version)


async def cache_latest_pointer(redis: aioredis.Redis, family_id: uuid.UUID, version: int) -> None:
    try:
        await redis.setex(
            _latest_key(family_id),
            settings.CACHE_TTL_SECONDS,
            str(version),
        )
    except Exception:
        logger.warning("cache_latest_write_failed", family_id=str(family_id))


async def update_cache_after_write(
    redis: aioredis.Redis, family_id: uuid.UUID, version: int, response: PlanVersionResponse
) -> None:
    await cache_plan(redis, family_id, version, response)
    await cache_latest_pointer(redis, family_id, version)
    try:
        await redis.sadd(_ACTIVE_PLANS_KEY, str(family_id))
    except Exception:
        logger.warning("cache_active_set_write_failed", family_id=str(family_id))


async def invalidate_cache_after_deactivation(
    redis: aioredis.Redis, family_id: uuid.UUID, version: int
) -> None:
    try:
        await redis.srem(_ACTIVE_PLANS_KEY, str(family_id))
        await redis.delete(_latest_key(family_id))
    except Exception:
        logger.warning("cache_invalidation_failed", family_id=str(family_id), version=version)
