"""Memoir FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router, legacy_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.db.base import Base
from app.db.session import engine
from app.services.seed import seed_prompts

import app.models  # noqa: F401  (populate metadata)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev/test convenience. Production uses Alembic migrations instead.
    if settings.ENVIRONMENT.lower() != "production":
        Base.metadata.create_all(bind=engine)
    db = None
    try:
        from app.db.session import SessionLocal

        db = SessionLocal()
        seed_prompts(db)
    except Exception:
        pass
    finally:
        if db:
            db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Memoir — Your Life. Your Stories. Your Legacy.",
        version=settings.APP_VERSION,
        description="AI 原生个人记忆、人生故事、家庭记忆与数字传承平台",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)

    # Legacy v0.1 API stays at its original paths.
    app.include_router(legacy_router)
    # New versioned API.
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/")
    def root():
        return {
            "message": "数字人生回忆录 API",
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "status": "running",
        }

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
