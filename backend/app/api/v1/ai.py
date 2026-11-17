"""AI Memory Engine endpoints (RAG Q&A + job tracking)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.retrieval import answer, retrieve
from app.core.deps import get_current_user, get_db
from app.models.ai import AIJob

router = APIRouter(prefix="/ai", tags=["ai-engine"])


class AskIn(BaseModel):
    question: str
    family_id: str | None = None
    top_k: int = 5


@router.post("/ask")
def ask(payload: AskIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    evidence = retrieve(db, user.id, payload.question, top_k=payload.top_k, family_id=payload.family_id)
    return answer(db, user.id, payload.question, evidence)


@router.get("/jobs/{job_id}")
def job_status(job_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(AIJob).filter(AIJob.id == job_id, AIJob.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "progress": job.progress,
        "attempts": job.attempts,
        "error": job.error,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(AIJob).filter(AIJob.id == job_id, AIJob.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status in ("completed", "failed"):
        raise HTTPException(status_code=400, detail="任务已结束")
    job.status = "cancelled"
    db.commit()
    return {"message": "任务已取消"}
