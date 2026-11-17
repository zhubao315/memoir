"""Story Studio schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PromptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    category_key: str
    question: str
    hint: str | None


class InterviewCreate(BaseModel):
    topic: str | None = None
    prompt_id: str | None = None
    family_id: str | None = None
    title: str | None = None


class InterviewAnswerIn(BaseModel):
    content: str = Field(min_length=1)
    recording_id: str | None = None
    finish: bool = False


class InterviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    topic: str | None
    title: str | None
    status: str
    current_prompt_id: str | None
    summary: str | None
    generated_story_id: str | None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: str
    content: str
    facts: dict | None
    follow_up: bool
    created_at: datetime


class StoryGenerateIn(BaseModel):
    mode: str = "first_person"
    # one of transcript|clean|first_person|third_person|literary|concise|documentary
    title: str | None = None
    source_memory_id: str | None = None
    source_recording_id: str | None = None
    source_interview_id: str | None = None
    prompt_version: str | None = None


class StoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str | None
    summary: str | None
    status: str
    current_version_id: str | None
    source_recording_id: str | None
    visibility: str


class StoryVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    story_id: str
    version_no: int
    mode: str
    content: str
    is_ai: bool
    provider: str | None
    model: str | None
    prompt_version: str | None
    needs_confirmation: list | None
    created_at: datetime


class VersionEditIn(BaseModel):
    content: str = Field(min_length=1)
    note: str | None = None
