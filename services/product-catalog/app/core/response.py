from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class APIErrorBody(BaseModel):
    code: str = Field(default="error")
    details: Any | None = None


class APIErrorResponse(BaseModel):
    success: bool = False
    message: str
    error: APIErrorBody


class APIError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "error",
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details


def success(
    data: Any = None,
    *,
    message: str = "OK",
    status_code: int = status.HTTP_200_OK,
) -> JSONResponse:
    payload = {"success": True, "message": message, "data": data}
    return JSONResponse(status_code=status_code, content=jsonable_encoder(payload))


def error(
    message: str,
    *,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    code: str = "error",
    details: Any | None = None,
) -> JSONResponse:
    payload = APIErrorResponse(
        message=message,
        error=APIErrorBody(code=code, details=details),
    )
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload),
    )
