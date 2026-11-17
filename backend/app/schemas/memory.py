"""Memory Vault schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MemoryIn(BaseModel):
    title: str | None = None
    raw_content: str | None = None
    occurred_at: str | None = None
    memory_type: str = "memory"
    mood: str = "neutral"
    location: dict[str, Any] | None = None
    tags: list[str] | None = None
    visibility: str = "private"
    family_id: str | None = None
    source: str = "manual"


class MemoryUpdate(BaseModel):
    title: str | None = None
    # raw_content is intentionally NOT updatable via AI paths; manual correction is allowed only
    # through a dedicated endpoint that logs an audit entry (原则 A).
    raw_content: str | None = None
    occurred_at: str | None = None
    memory_type: str | None = None
    mood: str | None = None
    location: dict[str, Any] | None = None
    tags: list[str] | None = None
    visibility: str | None = None


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    title: str | None
    raw_content: str | None
    ai_summary: str | None
    occurred_at: str | None
    memory_type: str
    mood: str
    location: dict | None
    tags: list | None
    visibility: str
    created_at: datetime


class PersonIn(BaseModel):
    name: str
    alias: list[str] | None = None
    notes: str | None = None
    birth_date: str | None = None


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    alias: list | None
    notes: str | None
    birth_date: str | None
