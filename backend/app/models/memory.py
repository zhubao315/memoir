"""Memory Vault, people graph, life stages (P1/P2)."""

from sqlalchemy import Column, Float, JSON, String, Text

from app.db.base import Base
from app.models.common import SoftDeleteMixin, TimestampMixin, UUIDMixin


class Memory(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "memories"
    user_id = Column(String, nullable=False, index=True)
    family_id = Column(String, nullable=True, index=True)
    creator_id = Column(String, nullable=False)
    source = Column(String, default="manual")  # manual|interview|recording|import
    source_ref = Column(String, nullable=True)
    title = Column(String, nullable=True)
    raw_content = Column(Text, nullable=True)     # user's original, never overwritten by AI
    ai_summary = Column(Text, nullable=True)
    occurred_at = Column(String, nullable=True)   # ISO date string
    memory_type = Column(String, default="memory")
    mood = Column(String, default="neutral")
    location = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    visibility = Column(String, default="private")  # private|family|public
    legacy_entry_id = Column(String, nullable=True, index=True)  # link to legacy entries.id


class MemoryLocation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "memory_locations"
    memory_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)


class MemoryRelation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "memory_relations"
    user_id = Column(String, nullable=False, index=True)
    from_memory_id = Column(String, nullable=False, index=True)
    to_memory_id = Column(String, nullable=False, index=True)
    relation = Column(String, default="related")  # related|similar|follows|about
    score = Column(Float, nullable=True)
    source = Column(String, default="auto")  # auto|manual


class Person(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "persons"
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    alias = Column(JSON, nullable=True)
    birth_date = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    avatar_url = Column(String, nullable=True)


class PersonRelation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "person_relations"
    user_id = Column(String, nullable=False, index=True)
    from_person_id = Column(String, nullable=False, index=True)
    to_person_id = Column(String, nullable=False, index=True)
    relation = Column(String, nullable=False)  # 父亲/母亲/配偶/朋友/...
    source = Column(String, default="manual")


class LifeStage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "life_stages"
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    order_index = Column(String, nullable=True)


class Milestone(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "milestones"
    user_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    occurred_at = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    memory_id = Column(String, nullable=True, index=True)
