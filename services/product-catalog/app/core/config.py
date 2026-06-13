from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    DATABASE_URL: str
    REDIS_URL: str
    KAFKA_BOOTSTRAP_SERVERS: str

    # Auth
    ADMIN_TOKEN: str

    # Business config
    ANNUAL_DISCOUNT_RATE: float = Field(default=0.17, ge=0.0, le=1.0)

    DB_POOL_SIZE: int = Field(default=5, ge=1)
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0)
    DB_POOL_TIMEOUT: int = Field(default=30, ge=1)

    OUTBOX_POLL_INTERVAL_SECONDS: int = Field(default=5, ge=1)
    OUTBOX_DEAD_LETTER_THRESHOLD: int = Field(default=10, ge=1)

    CACHE_TTL_SECONDS: int = Field(default=3600, ge=0)

    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
