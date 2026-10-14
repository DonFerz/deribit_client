from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения загружаются из файла переменных среды / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        validate_default=True,
    )

    # --- App ---
    app_name: str = "deribit-client"
    app_env: Literal["local", "dev", "staging", "prod"] = "local"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # --- Logging ---
    log_level: Literal["DEBUG", "INFO",
                       "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # --- Postgres ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "deribit"
    postgres_password: str = "deribit"
    postgres_db: str = "deribit"

    # --- Redis ---
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # --- Celery ---
    celery_fetch_interval_seconds: int = 60

    # --- Deribit ---
    deribit_base_url: str = "https://www.deribit.com/api/v2"
    deribit_request_timeout: int = 10
    deribit_tickers: list[str] = ["btc_usd", "eth_usd"]

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{quote_plus(self.postgres_user)}:"
            f"{quote_plus(self.postgres_password)}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
