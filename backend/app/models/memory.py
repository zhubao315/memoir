"""Memory Vault, people graph, life stages (P1/P2)."""

from sqlalchemy import Column, Float, Index, JSON, String, Text

from app.db.base import Base
from app.models.common import SoftDeleteMixin, TimestampMixin, UUIDMixin


class Memory(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "memories"
    # 复合索引服务于“按用户 + 未删除 + 时间倒序”的列表查询，所有隔离过滤都走索引。
    __table_args__ = (
        Index("ix_memories_user_deleted_created", "user_id", "deleted_at", "created_at"),
        Index("ix_memories_user_family", "user_id", "family_id"),
    )
    user_id = Column(String, nullable=False, index=True)
    family_id = Column(String, nullable=True, index=True)
    creator_id = Column(String, nullable=False)
    source = Column(String, default="manual")  # manual|interview|recording|import
    source_ref = Column(String, nullable=True)
    title = Column(String, nullable=True)
    # 原始内容由用户所有，AI 永不覆盖；ai_* / 实体 / 摘要均为可再生的衍生数据。
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
    # 归属跟随 memory：user_id 冗余存储以便直接做隔离过滤（与 memory.user_id 一致）。
    __table_args__ = (
        Index("ix_memory_locations_user_memory", "user_id", "memory_id"),
    )
    user_id = Column(String, nullable=False, index=True)
    memory_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)


class MemoryRelation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "memory_relations"
    __table_args__ = (
        Index("ix_memory_relations_user_from", "user_id", "from_memory_id"),
    )
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
