"""Application settings loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

# backend/app/core/config.py → backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Conductor API"
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")
    api_v1_prefix: str = "/api/v1"
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cors_origins: str = Field(
        default="http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:3000,http://localhost:3000",
        alias="CORS_ORIGINS",
    )

    # Database
    postgres_host: str = Field(default="127.0.0.1", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_user: str = Field(default="conductor", alias="POSTGRES_USER")
    postgres_password: str = Field(default="conductor", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="conductor", alias="POSTGRES_DB")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    # JWT (login later)
    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=30,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    # Conductor control plane (Redis)
    redis_url: str = Field(default="redis://127.0.0.1:6379/0", alias="REDIS_URL")
    conductor_commands_key: str = Field(
        default="conductor:commands",
        alias="CONDUCTOR_COMMANDS_KEY",
    )
    conductor_events_key: str = Field(
        default="conductor:events",
        alias="CONDUCTOR_EVENTS_KEY",
    )
    dashboard_user_id: str = Field(default="dashboard", alias="DASHBOARD_USER_ID")
    conductor_event_timeout_sec: float = Field(
        default=20.0,
        alias="CONDUCTOR_EVENT_TIMEOUT_SEC",
    )

    # Default Bybit deploy credentials (from env — not from browser)
    bybit_environment: str = Field(default="testnet", alias="BYBIT_ENVIRONMENT")
    bybit_api_key: str = Field(default="", alias="BYBIT_API_KEY")
    bybit_api_secret: str = Field(default="", alias="BYBIT_API_SECRET")
    bybit_testnet_api_key: str = Field(default="", alias="BYBIT_TESTNET_API_KEY")
    bybit_testnet_api_secret: str = Field(default="", alias="BYBIT_TESTNET_API_SECRET")
    bybit_product_type: str = Field(default="linear", alias="BYBIT_PRODUCT_TYPE")
    bybit_instrument_id: str = Field(
        default="BTCUSDT-LINEAR.BYBIT",
        alias="BYBIT_INSTRUMENT_ID",
    )

    def bybit_credentials(self) -> tuple[str, str]:
        env = self.bybit_environment.lower()
        if env == "testnet":
            key = self.bybit_testnet_api_key or self.bybit_api_key
            secret = self.bybit_testnet_api_secret or self.bybit_api_secret
        else:
            key = self.bybit_api_key
            secret = self.bybit_api_secret
        return key, secret

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
