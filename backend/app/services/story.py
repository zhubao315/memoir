"""Story orchestration: generation -> immutable version -> generation log (原则 A/C)."""

from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.ai.prompts.registry import PROMPT_VERSION
from app.ai.story_writer import generate_story
from app.models.ai import AIGenerationLog
from app.models.story import Story, StoryVersion
from app.models.media import Transcript


def _next_version_no(db: Session, story_id: str) -> int:
    last = (
        db.query(StoryVersion)
        .filter(StoryVersion.story_id == story_id)
        .order_by(StoryVersion.version_no.desc())
        .first()
    )
    return (last.version_no + 1) if last else 1


def create_story(
    db: Session,
    user_id: str,
    content: str,
    mode: str,
    *,
    title: str | None = None,
    family_id: str | None = None,
    source_memory_id: str | None = None,
    source_recording_id: str | None = None,
    source_interview_id: str | None = None,
    facts: dict | None = None,
) -> tuple[Story, StoryVersion]:
    draft = generate_story(content, mode, title=title, facts=facts)
    story = Story(
        user_id=user_id,
        family_id=family_id,
        title=title or (content[:24] + ("…" if len(content) > 24 else "")),
        status="draft",
        source_memory_id=source_memory_id,
        source_recording_id=source_recording_id,
        source_interview_id=source_interview_id,
        visibility="private",
    )
    db.add(story)
    db.flush()

    version = StoryVersion(
        story_id=story.id,
        version_no=_next_version_no(db, story.id),
        mode=mode,
        content=draft.content,
        is_ai=True,
        provider=draft.provider,
        model=draft.model,
        prompt_version=draft.prompt_version,
        needs_confirmation=draft.needs_confirmation,
        input_refs={
            "source_memory_id": source_memory_id,
            "source_recording_id": source_recording_id,
            "source_interview_id": source_interview_id,
        },
    )
    db.add(version)
    db.flush()

    log = AIGenerationLog(
        user_id=user_id,
        task="story",
        provider=draft.provider,
        model=draft.model,
        prompt_version=draft.prompt_version or PROMPT_VERSION,
        input_refs={"chars": len(content), "mode": mode},
        output=draft.content,
        status="success",
    )
    db.add(log)
    db.flush()

    story.current_version_id = version.id
    story.summary = draft.content[:160]
    version.generation_log_id = log.id
    db.commit()
    db.refresh(story)
    db.refresh(version)
    return story, version


def add_human_version(db: Session, story: Story, editor_id: str, content: str, note: str | None = None) -> StoryVersion:
    """Manual edit creates a NEW version; AI draft and raw input are never overwritten."""
    version = StoryVersion(
        story_id=story.id,
        version_no=_next_version_no(db, story.id),
        mode="human_edit",
        content=content,
        is_ai=False,
        editor_id=editor_id,
        note=note,
        input_refs={"based_on": story.current_version_id},
    )
    db.add(version)
    db.flush()
    story.current_version_id = version.id
    db.commit()
    db.refresh(version)
    return version


def get_story(db: Session, story_id: str, user_id: str) -> Story:
    story = (
        db.query(Story)
        .filter(Story.id == story_id, Story.user_id == user_id, Story.deleted_at.is_(None))
        .first()
    )
    if not story:
        raise HTTPException(status_code=404, detail="故事不存在")
    return story


def source_text(
    db: Session,
    user_id: str,
    recording_id: str | None = None,
    memory_id: str | None = None,
    interview_id: str | None = None,
) -> str:
    """读取「当前用户本人」的素材原文（IDOR 防护）。

    任何资源 id 都必须同时满足归属校验；跨用户或已删除的资源一律 404，
    不返回内容、也不泄漏资源是否存在。调用方必须显式传入 user_id。
    """
    if recording_id:
        from app.models.media import Recording

        rec = (
            db.query(Recording)
            .filter(
                Recording.id == recording_id,
                Recording.user_id == user_id,
                Recording.deleted_at.is_(None),
            )
            .first()
        )
        if not rec:
            raise HTTPException(status_code=404, detail="录音不存在")
        # 逐字稿同样做归属校验，避免被篡改的 recording_id 关联到他人文本。
        t = (
            db.query(Transcript)
            .filter(Transcript.recording_id == recording_id, Transcript.user_id == user_id)
            .order_by(Transcript.created_at.desc())
            .first()
        )
        if t:
            return t.content
        # 尚无逐字稿时保持原有回退语义：继续尝试其它来源。

    if memory_id:
        from app.models.memory import Memory

        m = (
            db.query(Memory)
            .filter(Memory.id == memory_id, Memory.user_id == user_id, Memory.deleted_at.is_(None))
            .first()
        )
        if not m:
            raise HTTPException(status_code=404, detail="记忆不存在")
        return m.raw_content or ""

    if interview_id:
        from app.models.story import Interview, InterviewMessage

        interview = (
            db.query(Interview)
            .filter(Interview.id == interview_id, Interview.user_id == user_id, Interview.deleted_at.is_(None))
            .first()
        )
        if not interview:
            raise HTTPException(status_code=404, detail="访谈不存在")
        msgs = (
            db.query(InterviewMessage)
            .filter(InterviewMessage.interview_id == interview_id, InterviewMessage.role == "interviewee")
            .order_by(InterviewMessage.created_at.asc())
            .all()
        )
        return "\n".join(m.content for m in msgs)
    return ""
