from collections.abc import Callable
from typing import Any, Generic, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel

from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    message: str | None = None
    data: T | None = None


async def respond(fn: Callable, *args: Any, **kwargs: Any) -> ApiResponse:
    try:
        result = await fn(*args, **kwargs)
        return ApiResponse(success=True, data=result)
    except HTTPException:
        # Re-raise — service layer raised an explicit HTTP error
        raise
    except Exception:
        logger.exception("unhandled_error", fn=fn.__name__)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
