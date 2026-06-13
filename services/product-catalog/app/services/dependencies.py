from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.config import settings
from app.core.database import get_session
from app.services.plan_service import PlanService


def get_plan_service(
    session: AsyncSession = Depends(get_session),
) -> PlanService:
    return PlanService(session=session, redis=get_redis(), settings=settings)
