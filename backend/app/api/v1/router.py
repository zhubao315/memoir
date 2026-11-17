"""v1 API aggregator."""

from fastapi import APIRouter

from app.api.v1 import (
    activity,
    ai,
    auth,
    book,
    dashboard,
    digital_legacy,
    family,
    media,
    memories,
    search,
    story,
    uploads,
)
from app.api.v1.legacy import router as legacy_router

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(memories.router)
api_router.include_router(media.router)
api_router.include_router(story.router)
api_router.include_router(family.router)
api_router.include_router(book.router)
api_router.include_router(digital_legacy.router)
api_router.include_router(dashboard.router)
api_router.include_router(ai.router)
api_router.include_router(search.router)
api_router.include_router(activity.router)
api_router.include_router(uploads.router)

# Legacy v0.1 REST API is mounted separately in main.py at its original /api paths.
__all__ = ["api_router", "legacy_router"]
