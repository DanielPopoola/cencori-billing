from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.cache import close_redis, init_redis
from app.core.database import engine
from app.core.logging import get_logger, setup_logging
from app.core.response import APIError, error

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup_begin")
    await init_redis()
    logger.info("startup_complete")
    yield
    logger.info("shutdown_begin")
    await close_redis()
    await engine.dispose()
    logger.info("shutdown_complete")


app = FastAPI(
    title="Cencori Product Catalog",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return error(exc.message, status_code=exc.status_code, code=exc.code, details=exc.details)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error(
        "Invalid request body",
        status_code=422,
        code="validation_error",
        details=exc.errors(),
    )


@app.get("/healthz", tags=["ops"])
async def healthz():
    return {"status": "ok"}
