"""Life Studio dashboard & data export."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_db

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.legacy_tables import Entry, Media, Tag
from app.models.media import MediaAsset
from app.models.memory import LifeStage, Memory, Milestone
from app.models.story import Interview, Prompt, Story

router = APIRouter(prefix="/dashboard", tags=["life-studio"])


@router.get("/summary")
def summary(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return _summary(user, db)


def _summary(user, db):
    memories = db.query(func.count(Memory.id)).filter(Memory.user_id == user.id, Memory.deleted_at.is_(None)).scalar()
    legacy_entries = db.query(func.count(Entry.id)).filter(Entry.user_id == user.id).scalar()
    stories = db.query(func.count(Story.id)).filter(Story.user_id == user.id, Story.deleted_at.is_(None)).scalar()
    photos = db.query(func.count(MediaAsset.id)).filter(MediaAsset.user_id == user.id, MediaAsset.media_type == "photo").scalar()
    audios = db.query(func.count(MediaAsset.id)).filter(MediaAsset.user_id == user.id, MediaAsset.media_type == "audio").scalar()
    videos = db.query(func.count(MediaAsset.id)).filter(MediaAsset.user_id == user.id, MediaAsset.media_type == "video").scalar()
    pending = db.query(func.count(Interview.id)).filter(Interview.user_id == user.id, Interview.status == "active").scalar()
    daily_prompt = db.query(Prompt).filter(Prompt.enabled.is_(True)).order_by(func.random()).first()
    recent = db.query(Memory).filter(Memory.user_id == user.id, Memory.deleted_at.is_(None)).order_by(Memory.created_at.desc()).limit(5).all()
    recent_stories = db.query(Story).filter(Story.user_id == user.id, Story.deleted_at.is_(None)).order_by(Story.created_at.desc()).limit(5).all()
    milestones = db.query(Milestone).filter(Milestone.user_id == user.id, Milestone.deleted_at.is_(None)).limit(5).all()
    stages = db.query(LifeStage).filter(LifeStage.user_id == user.id).all()
    return {
        "counts": {
            "memories": memories + legacy_entries,
            "stories": stories,
            "photos": photos,
            "audios": audios,
            "videos": videos,
            "pending_interviews": pending,
        },
        "daily_prompt": {"id": daily_prompt.id, "question": daily_prompt.question} if daily_prompt else None,
        "recent_memories": [{"id": m.id, "title": m.title, "occurred_at": m.occurred_at} for m in recent],
        "recent_stories": [{"id": s.id, "title": s.title, "status": s.status} for s in recent_stories],
        "milestones": [{"id": m.id, "title": m.title, "occurred_at": m.occurred_at} for m in milestones],
        "life_stages": [{"id": s.id, "name": s.name, "start_date": s.start_date, "end_date": s.end_date} for s in stages],
    }


@router.get("/export")
def export_data(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Full personal data export (memory + metadata), GDPR-style."""
    data = {
        "user": {"id": user.id, "username": user.username, "email": user.email},
        "entries": [e.__dict__ for e in db.query(Entry).filter(Entry.user_id == user.id).all()],
        "media": [m.__dict__ for m in db.query(Media).filter(Media.user_id == user.id).all()],
        "tags": [t.__dict__ for t in db.query(Tag).filter(Tag.user_id == user.id).all()],
        "memories": [m.__dict__ for m in db.query(Memory).filter(Memory.user_id == user.id).all()],
        "stories": [s.__dict__ for s in db.query(Story).filter(Story.user_id == user.id).all()],
    }
    out_dir = settings.upload_dir / "exports" / user.id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "memoir-data-export.json"
    path.write_text(json.dumps(data, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
    return FileResponse(str(path), filename="memoir-data-export.json")
