"""Story Studio: prompt bank, AI interview, stories & immutable versions (P1 core loop)."""

from sqlalchemy import Boolean, Column, Integer, JSON, String, Text

from app.db.base import Base
from app.models.common import SoftDeleteMixin, TimestampMixin, UUIDMixin


class PromptCategory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "prompt_categories"
    key = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)


class Prompt(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "prompts"
    category_key = Column(String, nullable=False, index=True)
    question = Column(Text, nullable=False)
    hint = Column(Text, nullable=True)
    is_system = Column(Boolean, default=True)
    author_id = Column(String, nullable=True)
    family_id = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    times_used = Column(Integer, default=0)
    quality_score = Column(Integer, nullable=True)


class PromptFavorite(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "prompt_favorites"
    user_id = Column(String, nullable=False, index=True)
    prompt_id = Column(String, nullable=False, index=True)


class PromptVote(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "prompt_votes"
    prompt_id = Column(String, nullable=False, index=True)
    family_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    value = Column(Integer, default=1)


class Interview(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "interviews"
    user_id = Column(String, nullable=False, index=True)
    family_id = Column(String, nullable=True, index=True)
    topic = Column(String, nullable=True)
    title = Column(String, nullable=True)
    status = Column(String, default="active")  # active|paused|completed|archived
    current_prompt_id = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    generated_story_id = Column(String, nullable=True, index=True)


class InterviewMessage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "interview_messages"
    interview_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)  # interviewer | interviewee | system
    content = Column(Text, nullable=False)
    prompt_id = Column(String, nullable=True)
    recording_id = Column(String, nullable=True)
    facts = Column(JSON, nullable=True)  # extracted time/person/place/event/emotion
    follow_up = Column(Boolean, default=False)


class Story(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "stories"
    user_id = Column(String, nullable=False, index=True)
    family_id = Column(String, nullable=True, index=True)
    storyteller_id = Column(String, nullable=True)
    title = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    status = Column(String, default="draft")  # draft|in_review|published
    current_version_id = Column(String, nullable=True)
    source_memory_id = Column(String, nullable=True, index=True)
    source_recording_id = Column(String, nullable=True, index=True)
    source_interview_id = Column(String, nullable=True, index=True)
    visibility = Column(String, default="private")  # private|family|public


class StoryVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "story_versions"
    story_id = Column(String, nullable=False, index=True)
    version_no = Column(Integer, nullable=False)
    mode = Column(String, default="clean")  # transcript|clean|first_person|third_person|literary|concise|documentary
    content = Column(Text, nullable=False)
    is_ai = Column(Boolean, default=True)
    editor_id = Column(String, nullable=True)
    provider = Column(String, nullable=True)
    model = Column(String, nullable=True)
    prompt_version = Column(String, nullable=True)
    generation_log_id = Column(String, nullable=True, index=True)
    input_refs = Column(JSON, nullable=True)
    needs_confirmation = Column(JSON, nullable=True)  # AI 不确定项标记，供人工确认
    note = Column(Text, nullable=True)
