"""Background AI job orchestration (modular monolith, ARQ-ready interface)."""

from __future__ import annotations

import traceback

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.ai.extraction import extract_facts
from app.ai.factory import get_llm
from app.ai.transcription import transcribe
from app.core.config import settings
from app.core.security import utcnow
from app.db.session import SessionLocal
from app.models.ai import AIJob, AIGenerationLog, Embedding, MemoryEntity
from app.models.media import MediaAsset, Recording, Transcript
from app.models.memory import Memory

from datetime import datetime


def create_job(db: Session, user_id: str, kind: str, input_refs: dict, idempotency_key: str | None = None) -> AIJob:
    if idempotency_key:
        existing = db.query(AIJob).filter(AIJob.idempotency_key == idempotency_key).first()
        if existing:
            return existing
    job = AIJob(
        user_id=user_id,
        kind=kind,
        status="pending",
        input_refs=input_refs,
        idempotency_key=idempotency_key,
        max_retries=settings.TASK_MAX_RETRIES,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def enqueue(background: BackgroundTasks, job_id: str) -> None:
    background.add_task(run_job, job_id)


def run_job(job_id: str) -> None:
    """Runs in background; each job has its own DB session and is idempotent."""
    db = SessionLocal()
    try:
        job = db.query(AIJob).filter(AIJob.id == job_id).first()
        if not job or job.status in ("completed", "cancelled"):
            return
        job.status = "processing"
        job.started_at = datetime.utcnow().isoformat()
        job.attempts += 1
        db.commit()

        if job.kind == "transcription":
            _transcription(db, job)
        elif job.kind == "memory_extraction":
            _extraction(db, job)
        elif job.kind == "embedding":
            _embedding(db, job)
        else:
            raise ValueError(f"unknown job kind: {job.kind}")

        job.status = "completed"
        job.progress = 100
        job.finished_at = datetime.utcnow().isoformat()
        db.commit()
    except Exception as exc:  # pragma: no cover - error path
        try:
            job = db.query(AIJob).filter(AIJob.id == job_id).first()
            if job:
                job.error = traceback.format_exc()[-2000:]
                if job.attempts < job.max_retries:
                    job.status = "pending"
                else:
                    job.status = "failed"
                job.finished_at = datetime.utcnow().isoformat()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _transcription(db: Session, job: AIJob) -> None:
    refs = job.input_refs or {}
    asset = db.query(MediaAsset).filter(MediaAsset.id == refs.get("media_asset_id")).first()
    recording = db.query(Recording).filter(Recording.id == refs.get("recording_id")).first()
    if not asset or not recording:
        raise ValueError("media asset or recording not found")
    from app.storage import get_storage

    data = get_storage().read(asset.storage_key)
    from app.ai.factory import get_asr

    engine = get_asr().name
    text, raw = transcribe(data, asset.original_filename or "audio", asset.mime_type or "audio/mpeg")
    db.add(
        Transcript(
            recording_id=recording.id,
            user_id=job.user_id,
            content=text,
            engine=engine,
            raw_response=raw,
        )
    )
    recording.status = "transcribed"
    job.result_refs = {"recording_id": recording.id}
    db.commit()


def _extraction(db: Session, job: AIJob) -> None:
    refs = job.input_refs or {}
    memory = db.query(Memory).filter(Memory.id == refs.get("memory_id")).first()
    if not memory:
        raise ValueError("memory not found")
    facts = extract_facts(memory.raw_content or "")
    for key, values in facts.items():
        for value in values:
            db.add(
                MemoryEntity(
                    user_id=job.user_id,
                    memory_id=memory.id,
                    entity_type=key,
                    name=str(value),
                    confidence=1.0,
                    source="ai",
                )
            )
    memory.ai_summary = "; ".join(f"{k}: {', '.join(v)}" for k, v in facts.items() if v) or None
    db.add(
        AIGenerationLog(
            user_id=job.user_id,
            job_id=job.id,
            task="extract",
            provider="mock",
            model="rule-based",
            input_refs=refs,
            output=str(facts),
        )
    )
    job.result_refs = {"entities": sum(len(v) for v in facts.values())}
    db.commit()


def _embedding(db: Session, job: AIJob) -> None:
    refs = job.input_refs or {}
    resource_type = refs.get("resource_type")
    resource_id = refs.get("resource_id")
    text = ""
    if resource_type == "memory":
        m = db.query(Memory).filter(Memory.id == resource_id).first()
        text = (m.title or "") + "\n" + (m.raw_content or "") if m else ""
    elif resource_type == "story":
        from app.models.story import Story, StoryVersion

        s = db.query(Story).filter(Story.id == resource_id).first()
        if s and s.current_version_id:
            v = db.query(StoryVersion).filter(StoryVersion.id == s.current_version_id).first()
            text = (s.title or "") + "\n" + (v.content if v else "")
    if not text:
        raise ValueError("no text to embed")
    llm = get_llm()
    vec = llm.embed([text])[0]
    existing = (
        db.query(Embedding)
        .filter(Embedding.user_id == job.user_id, Embedding.resource_type == resource_type, Embedding.resource_id == resource_id)
        .first()
    )
    if existing:
        existing.vector = vec
        existing.model = llm.name
        existing.dim = len(vec)
    else:
        db.add(
            Embedding(
                user_id=job.user_id,
                family_id=refs.get("family_id"),
                resource_type=resource_type,
                resource_id=resource_id,
                model=llm.name,
                dim=len(vec),
                vector=vec,
            )
        )
    job.result_refs = {"dim": len(vec)}
    db.commit()
