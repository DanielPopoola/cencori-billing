from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.cache import close_redis, init_redis
from app.core.database import engine
from app.core.logging import get_logger, setup_logging

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


@app.get("/healthz", tags=["ops"])
async def healthz():
    return {"status": "ok"}
