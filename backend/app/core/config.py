"""Centralized, environment-driven configuration (P0: de-hardcode secrets/paths)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    ENVIRONMENT: str = "development"  # development | staging | production
    APP_NAME: str = "Memoir"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # ---- Security (P0) ----
    SECRET_KEY: str = "dev-only-insecure-secret-key-change-me-please-123456"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    JWT_ALGORITHM: str = "HS256"
    # login rate limiting
    LOGIN_RATE_LIMIT: int = 10  # attempts per window
    LOGIN_RATE_WINDOW_SECONDS: int = 60

    # ---- CORS (P0) ----
    # comma separated origins. "*" is rejected when credentials are enabled.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000"
    CORS_ALLOW_CREDENTIALS: bool = True

    # ---- Database ----
    # SQLite for dev/test; set postgresql+psycopg://... for production.
    DATABASE_URL: str = "sqlite:///./memoir.db"

    # ---- Storage (P0) ----
    STORAGE_BACKEND: str = "local"  # local | s3
    LOCAL_STORAGE_DIR: str = "./uploads"
    S3_ENDPOINT_URL: str = ""
    S3_BUCKET: str = "memoir"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "us-east-1"
    MEDIA_URL_TTL_SECONDS: int = 900  # signed URL lifetime
    MAX_UPLOAD_BYTES: int = 100 * 1024 * 1024  # 100 MB

    # ---- AI Providers (no keys => deterministic Mock, never fake real service) ----
    AI_PROVIDER: str = "mock"  # mock | openai_compatible | anthropic_compatible | local
    AI_BASE_URL: str = ""
    AI_API_KEY: str = ""
    AI_MODEL_STORY: str = "memoir-story-v1"
    AI_MODEL_FAST: str = "memoir-fast-v1"
    AI_MODEL_EMBEDDING: str = "memoir-embedding-v1"
    ASR_PROVIDER: str = "mock"  # mock | openai_compatible (whisper)
    ASR_BASE_URL: str = ""
    ASR_API_KEY: str = ""
    ASR_MODEL: str = "whisper-1"

    # ---- Media / tasks ----
    MAX_AUDIO_SECONDS: int = 30 * 60  # Remento-style 30 min cap
    TASK_MAX_RETRIES: int = 3

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _parse_cors(cls, v: str) -> str:
        return v

    @model_validator(mode="after")
    def _check_secret(self) -> "Settings":
        if self.ENVIRONMENT.lower() in ("production", "prod", "staging"):
            if not os.getenv("SECRET_KEY") or len(self.SECRET_KEY) < 32:
                raise RuntimeError(
                    "SECRET_KEY must be set via environment (>=32 chars) in production."
                )
            if "change" in self.SECRET_KEY.lower() or "insecure" in self.SECRET_KEY.lower():
                raise RuntimeError("SECRET_KEY is a known placeholder; choose a strong random value.")
            if "*" in self.CORS_ORIGINS and self.CORS_ALLOW_CREDENTIALS:
                raise RuntimeError("CORS '*' cannot be combined with credentials in production.")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def upload_dir(self) -> Path:
        return Path(self.LOCAL_STORAGE_DIR)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
