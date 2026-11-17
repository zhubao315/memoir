"""Legacy v0.1 tables — schema kept EXACTLY compatible with the shipped SQLite DB.

These tables are never dropped. The legacy REST API (/api/entries, /api/tags, ...)
continues to work against them. New features use the domain tables in this package.
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Entry(Base):
    __tablename__ = "entries"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    title = Column(String, nullable=False)
    content = Column(Text)
    entry_date = Column(String, nullable=False)
    entry_type = Column(String, default="memory")
    mood = Column(String, default="neutral")
    location = Column(JSON, default=dict)
    tags = Column(JSON, default=list)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Tag(Base):
    __tablename__ = "tags"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    color = Column(String, default="#6366f1")
    icon = Column(String)
    created_at = Column(DateTime, default=func.now())


class Media(Base):
    __tablename__ = "media"

    id = Column(String, primary_key=True, default=_uuid)
    entry_id = Column(String, ForeignKey("entries.id"))
    user_id = Column(String, ForeignKey("users.id"))
    filename = Column(String, nullable=False)
    file_type = Column(String, default="photo")
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String)
    caption = Column(Text)
    taken_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
