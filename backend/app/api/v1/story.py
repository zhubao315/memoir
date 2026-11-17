"""Story Studio: prompt bank, AI interview, recordings, stories & versions."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.extraction import extract_facts
from app.ai.interviewer import next_question
from app.core.deps import get_current_user, get_db
from app.core.security import utcnow
from app.models.media import MediaAsset, Recording, Transcript
from app.models.story import (
    Interview,
    InterviewMessage,
    Prompt,
    PromptCategory,
    PromptFavorite,
    Story,
    StoryVersion,
)
from app.schemas.story import (
    InterviewAnswerIn,
    InterviewCreate,
    InterviewOut,
    MessageOut,
    PromptOut,
    StoryGenerateIn,
    StoryOut,
    StoryVersionOut,
    VersionEditIn,
)
from app.services import story as story_service
from app.services.media import signed_url_for
from app.services.tasks import create_job, enqueue
from app.models.ai import AIGenerationLog

router = APIRouter(prefix="/story", tags=["story-studio"])


class VisibilityIn(BaseModel):
    visibility: str  # private | family | public


class RegenerateIn(BaseModel):
    mode: str = "first_person"
    note: str | None = None


# ---------------- Prompt bank ----------------
@router.get("/prompts/categories")
def categories(db: Session = Depends(get_db)):
    return db.query(PromptCategory).order_by(PromptCategory.sort_order).all()


@router.get("/prompts", response_model=List[PromptOut])
def list_prompts(
    category: str | None = None,
    favorite: bool = False,
    limit: int = 20,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Prompt).filter(Prompt.enabled.is_(True))
    if category:
        q = q.filter(Prompt.category_key == category)
    if favorite:
        ids = [r.prompt_id for r in db.query(PromptFavorite).filter(PromptFavorite.user_id == user.id).all()]
        q = q.filter(Prompt.id.in_(ids))
    return q.order_by(Prompt.times_used.asc()).limit(limit).all()


@router.post("/prompts/{prompt_id}/favorite")
def favorite_prompt(prompt_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    exists = db.query(PromptFavorite).filter(PromptFavorite.user_id == user.id, PromptFavorite.prompt_id == prompt_id).first()
    if exists:
        db.delete(exists)
        db.commit()
        return {"favorited": False}
    db.add(PromptFavorite(user_id=user.id, prompt_id=prompt_id))
    db.commit()
    return {"favorited": True}


# ---------------- Interview ----------------
@router.post("/interviews", response_model=InterviewOut, status_code=201)
def create_interview(payload: InterviewCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    prompt = None
    if payload.prompt_id:
        prompt = db.query(Prompt).filter(Prompt.id == payload.prompt_id).first()
    elif payload.topic:
        prompt = db.query(Prompt).filter(Prompt.category_key == payload.topic, Prompt.enabled.is_(True)).first()
    question = prompt.question if prompt else "能和我讲讲你人生中印象最深的一段经历吗？"
    interview = Interview(
        user_id=user.id,
        family_id=payload.family_id,
        topic=payload.topic,
        title=payload.title or (payload.topic or "我的人生故事"),
        current_prompt_id=prompt.id if prompt else None,
        status="active",
    )
    db.add(interview)
    db.flush()
    db.add(InterviewMessage(interview_id=interview.id, role="interviewer", content=question, prompt_id=prompt.id if prompt else None))
    db.commit()
    db.refresh(interview)
    return interview


@router.get("/interviews", response_model=List[InterviewOut])
def list_interviews(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Interview).filter(Interview.user_id == user.id, Interview.deleted_at.is_(None)).order_by(Interview.created_at.desc()).all()


@router.get("/interviews/{interview_id}", response_model=InterviewOut)
def get_interview(interview_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    obj = db.query(Interview).filter(Interview.id == interview_id, Interview.user_id == user.id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="访谈不存在")
    return obj


@router.get("/interviews/{interview_id}/messages", response_model=List[MessageOut])
def get_messages(interview_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    obj = db.query(Interview).filter(Interview.id == interview_id, Interview.user_id == user.id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="访谈不存在")
    return db.query(InterviewMessage).filter(InterviewMessage.interview_id == interview_id).order_by(InterviewMessage.created_at.asc()).all()


@router.post("/interviews/{interview_id}/answer", response_model=List[MessageOut])
def answer(interview_id: str, payload: InterviewAnswerIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id, Interview.user_id == user.id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="访谈不存在")
    if interview.status != "active":
        raise HTTPException(status_code=400, detail="访谈已结束或暂停")
    # 回答中引用的录音必须属于当前用户，禁止挂载他人录音 id（IDOR 防护）。
    if payload.recording_id:
        rec = (
            db.query(Recording)
            .filter(
                Recording.id == payload.recording_id,
                Recording.user_id == user.id,
                Recording.deleted_at.is_(None),
            )
            .first()
        )
        if not rec:
            raise HTTPException(status_code=404, detail="录音不存在")

    facts = extract_facts(payload.content)
    history = [{"role": m.role, "content": m.content} for m in db.query(InterviewMessage).filter(InterviewMessage.interview_id == interview_id).all()]
    db.add(
        InterviewMessage(
            interview_id=interview_id,
            role="interviewee",
            content=payload.content,
            recording_id=payload.recording_id,
            facts=facts,
        )
    )
    if payload.finish:
        interview.status = "completed"
        db.commit()
        return db.query(InterviewMessage).filter(InterviewMessage.interview_id == interview_id).order_by(InterviewMessage.created_at.asc()).all()

    question, reason = next_question(history, payload.content, facts, interview.topic)
    if question:
        db.add(InterviewMessage(interview_id=interview_id, role="interviewer", content=question, follow_up=True))
    else:
        interview.status = "completed"
    db.commit()
    return db.query(InterviewMessage).filter(InterviewMessage.interview_id == interview_id).order_by(InterviewMessage.created_at.asc()).all()


@router.post("/interviews/{interview_id}/pause")
def pause(interview_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id, Interview.user_id == user.id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="访谈不存在")
    interview.status = "paused" if interview.status == "active" else "active"
    db.commit()
    return {"status": interview.status}


# ---------------- Recording ----------------
class RecordingIn(BaseModel):
    media_asset_id: str
    prompt_id: str | None = None
    interview_id: str | None = None
    duration_seconds: float | None = None


class RecordingOut(BaseModel):
    id: str
    status: str
    duration_seconds: float | None
    media_asset_id: str | None
    error: str | None = None  # 转写失败原因，供前端明确展示「失败」状态

    class Config:
        from_attributes = True


@router.post("/recordings", response_model=RecordingOut, status_code=201)
def create_recording(payload: RecordingIn, background: BackgroundTasks, user=Depends(get_current_user), db: Session = Depends(get_db)):
    asset = (
        db.query(MediaAsset)
        .filter(
            MediaAsset.id == payload.media_asset_id,
            MediaAsset.user_id == user.id,
            MediaAsset.deleted_at.is_(None),
        )
        .first()
    )
    if not asset:
        raise HTTPException(status_code=404, detail="媒体资产不存在")
    # 关联的访谈同样必须归属当前用户，避免通过 recording 间接引用他人访谈。
    if payload.interview_id:
        interview = (
            db.query(Interview)
            .filter(
                Interview.id == payload.interview_id,
                Interview.user_id == user.id,
                Interview.deleted_at.is_(None),
            )
            .first()
        )
        if not interview:
            raise HTTPException(status_code=404, detail="访谈不存在")
    rec = Recording(
        user_id=user.id,
        family_id=asset.family_id,
        media_asset_id=asset.id,
        interview_id=payload.interview_id,
        prompt_id=payload.prompt_id,
        duration_seconds=payload.duration_seconds,
        mime_type=asset.mime_type,
        status="uploaded",
    )
    db.add(rec)
    db.flush()
    job = create_job(db, user.id, "transcription", {"recording_id": rec.id, "media_asset_id": asset.id}, idempotency_key=f"transcript:{rec.id}")
    enqueue(background, job.id)
    rec.status = "transcribing"
    db.commit()
    db.refresh(rec)
    return rec


@router.get("/recordings/{recording_id}")
def get_recording(recording_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    rec = (
        db.query(Recording)
        .filter(Recording.id == recording_id, Recording.user_id == user.id, Recording.deleted_at.is_(None))
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="录音不存在")
    # 逐字稿也按 user_id 过滤；即使录制归属被篡改也不会读到他人文本。
    transcripts = (
        db.query(Transcript)
        .filter(Transcript.recording_id == rec.id, Transcript.user_id == user.id)
        .order_by(Transcript.created_at.desc())
        .all()
    )
    asset = None
    if rec.media_asset_id:
        asset = (
            db.query(MediaAsset)
            .filter(MediaAsset.id == rec.media_asset_id, MediaAsset.user_id == user.id, MediaAsset.deleted_at.is_(None))
            .first()
        )
    return {
        "recording": RecordingOut.model_validate(rec),
        "transcripts": [
            {
                "id": t.id,
                "content": t.content,
                "engine": t.engine,  # 真实 ASR 引擎名，前端如实展示
                "is_corrected": bool(t.is_corrected),
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in transcripts
        ],
        # 原始录音的短时效播放地址（仅资产所有者可见），供 Lightbox 播放。
        "play_url": signed_url_for(asset) if asset else '',
    }


class TranscriptCorrectIn(BaseModel):
    content: str = Field(min_length=1)


@router.put("/transcripts/{transcript_id}")
def correct_transcript(transcript_id: str, payload: TranscriptCorrectIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.query(Transcript).filter(Transcript.id == transcript_id, Transcript.user_id == user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="逐字稿不存在")
    # 双重归属校验：逐字稿关联的录音也必须属于当前用户。
    rec = (
        db.query(Recording)
        .filter(Recording.id == t.recording_id, Recording.user_id == user.id, Recording.deleted_at.is_(None))
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="录音不存在")
    # 事实保护：原始 ASR 逐字稿不覆盖；人工修正另存为一条带 is_corrected 的新记录。
    corrected = Transcript(
        recording_id=t.recording_id,
        user_id=user.id,
        content=payload.content,
        language=t.language,
        engine=t.engine,
        is_corrected=True,
    )
    db.add(corrected)
    db.commit()
    db.refresh(corrected)
    return {"message": "逐字稿已修正（原始录音与原始转写保持不变）", "id": corrected.id}


# ---------------- Story generation ----------------
@router.post("/stories/generate", response_model=StoryOut, status_code=201)
def generate(payload: StoryGenerateIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    # 素材归属强制校验（IDOR 防护）：跨用户的 recording/memory/interview 会返回 404。
    raw = story_service.source_text(
        db,
        user.id,
        payload.source_recording_id,
        payload.source_memory_id,
        payload.source_interview_id,
    )
    if not raw.strip():
        raise HTTPException(status_code=400, detail="没有可生成故事的原始内容")
    story, _ = story_service.create_story(
        db,
        user.id,
        raw,
        payload.mode,
        title=payload.title,
        source_memory_id=payload.source_memory_id,
        source_recording_id=payload.source_recording_id,
        source_interview_id=payload.source_interview_id,
    )
    job = create_job(db, user.id, "embedding", {"resource_type": "story", "resource_id": story.id})
    # embedding job runs synchronously here to keep citations available immediately
    from app.services.tasks import run_job

    run_job(job.id)
    return story


@router.get("/stories", response_model=List[StoryOut])
def list_stories(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Story).filter(Story.user_id == user.id, Story.deleted_at.is_(None)).order_by(Story.created_at.desc()).all()


@router.get("/stories/{story_id}", response_model=StoryOut)
def get_story(story_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return story_service.get_story(db, story_id, user.id)


@router.get("/stories/{story_id}/versions", response_model=List[StoryVersionOut])
def versions(story_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    story_service.get_story(db, story_id, user.id)
    return db.query(StoryVersion).filter(StoryVersion.story_id == story_id).order_by(StoryVersion.version_no.asc()).all()


@router.post("/stories/{story_id}/versions", response_model=StoryVersionOut, status_code=201)
def edit_version(story_id: str, payload: VersionEditIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    story = story_service.get_story(db, story_id, user.id)
    version = story_service.add_human_version(db, story, user.id, payload.content, payload.note)
    return version


@router.post("/stories/{story_id}/versions/{version_id}/restore", response_model=StoryOut)
def restore_version(story_id: str, version_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    story = story_service.get_story(db, story_id, user.id)
    version = db.query(StoryVersion).filter(StoryVersion.id == version_id, StoryVersion.story_id == story_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    story.current_version_id = version.id
    db.commit()
    db.refresh(story)
    return story


@router.get("/stories/{story_id}/current")
def current_version(story_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    story = story_service.get_story(db, story_id, user.id)
    version = (
        db.query(StoryVersion)
        .filter(StoryVersion.id == story.current_version_id, StoryVersion.story_id == story.id)
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="当前版本不存在")
    return version


@router.post("/stories/{story_id}/regenerate", response_model=StoryVersionOut, status_code=201)
def regenerate(story_id: str, payload: RegenerateIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a NEW AI version from the original source using another narrative style."""
    story = story_service.get_story(db, story_id, user.id)
    raw = story_service.source_text(db, story.source_recording_id, story.source_memory_id, story.source_interview_id)
    if not raw.strip():
        # Fallback: rewrite the current version (never overwrites it).
        current = db.query(StoryVersion).filter(StoryVersion.id == story.current_version_id).first()
        raw = current.content if current else ""
    if not raw.strip():
        raise HTTPException(status_code=400, detail="没有可用的原始内容")
    from app.ai.story_writer import generate_story

    draft = generate_story(raw, payload.mode, title=story.title)
    version = StoryVersion(
        story_id=story.id,
        version_no=story_service._next_version_no(db, story.id),
        mode=payload.mode,
        content=draft.content,
        is_ai=True,
        provider=draft.provider,
        model=draft.model,
        prompt_version=draft.prompt_version,
        needs_confirmation=draft.needs_confirmation,
        note=payload.note or f"重新生成 · {payload.mode}",
        input_refs={"source_story_id": story.id},
    )
    db.add(version)
    db.flush()
    db.add(
        AIGenerationLog(
            user_id=user.id, job_id=None, task="story_regenerate", provider=draft.provider,
            model=draft.model, prompt_version=draft.prompt_version,
            input_refs={"story_id": story.id, "mode": payload.mode}, output=draft.content,
        )
    )
    story.current_version_id = version.id
    db.commit()
    db.refresh(version)
    return version


@router.put("/stories/{story_id}/visibility", response_model=StoryOut)
def set_visibility(story_id: str, payload: VisibilityIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.visibility not in ("private", "family", "public"):
        raise HTTPException(status_code=400, detail="可见性必须为 private / family / public")
    story = story_service.get_story(db, story_id, user.id)
    story.visibility = payload.visibility
    if payload.visibility in ("family", "public") and story.status == "draft":
        story.status = "in_review"
    db.commit()
    db.refresh(story)
    return story


@router.delete("/stories/{story_id}")
def delete_story(story_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    story = story_service.get_story(db, story_id, user.id)
    story.deleted_at = utcnow()
    db.commit()
    return {"message": "故事已移入草稿箱"}

