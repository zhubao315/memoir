"""AI job tracking, provider configs, generation logs, embeddings (原则 C)."""

from sqlalchemy import Column, Float, Integer, JSON, String, Text

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDMixin


class AIProvider(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ai_providers"
    key = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    kind = Column(String, nullable=False)  # openai_compatible|anthropic_compatible|local|mock
    base_url = Column(String, nullable=True)
    model = Column(String, nullable=True)
    enabled = Column(Integer, default=1)
    # API key 只从环境变量读取，不入库，不回显。


class AIJob(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ai_jobs"
    user_id = Column(String, nullable=False, index=True)
    kind = Column(String, nullable=False, index=True)
    # transcription|story_generation|memory_extraction|embedding|image_analysis|book_render
    status = Column(String, default="pending", index=True)
    # pending|processing|completed|failed|cancelled
    progress = Column(Integer, default=0)
    input_refs = Column(JSON, nullable=True)
    result_refs = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    attempts = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    idempotency_key = Column(String, nullable=True, unique=True, index=True)
    started_at = Column(String, nullable=True)
    finished_at = Column(String, nullable=True)


class AIGenerationLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ai_generation_logs"
    user_id = Column(String, nullable=False, index=True)
    job_id = Column(String, nullable=True, index=True)
    task = Column(String, nullable=False)  # interview_question|story|summary|extract|embed
    provider = Column(String, nullable=True)
    model = Column(String, nullable=True)
    prompt_version = Column(String, nullable=True)
    input_refs = Column(JSON, nullable=True)
    output = Column(Text, nullable=True)
    status = Column(String, default="success")
    error = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)


class PromptTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "prompt_templates"
    key = Column(String, nullable=False, unique=True, index=True)
    version = Column(String, nullable=False, default="v1")
    task = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    active = Column(Integer, default=1)


class MemoryEntity(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "memory_entities"
    user_id = Column(String, nullable=False, index=True)
    memory_id = Column(String, nullable=True, index=True)
    entity_type = Column(String, nullable=False)  # person|place|event|time|emotion|thing
    name = Column(String, nullable=False)
    value = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    source = Column(String, default="ai")


class Embedding(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "embeddings"
    user_id = Column(String, nullable=False, index=True)
    family_id = Column(String, nullable=True, index=True)
    resource_type = Column(String, nullable=False)  # memory|story|transcript
    resource_id = Column(String, nullable=False, index=True)
    model = Column(String, nullable=True)
    dim = Column(Integer, nullable=True)
    vector = Column(JSON, nullable=True)  # JSON array; pgvector column added in prod migration
