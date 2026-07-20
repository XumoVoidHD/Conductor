"""Application settings loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

# api/app/core/config.py → api/
API_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(API_ROOT / ".env", ".env"),
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
