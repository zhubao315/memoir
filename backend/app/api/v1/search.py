"""Global search across the current user's memories, stories, people and media."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.memory import Memory, Person
from app.models.media import MediaAsset
from app.models.story import Story, StoryVersion

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search(q: str, limit: int = 30, user=Depends(get_current_user), db: Session = Depends(get_db)):
    q = q.strip()
    if not q:
        return {"query": q, "results": []}
    like = f"%{q}%"
    results = []

    for m in db.query(Memory).filter(
        Memory.user_id == user.id, Memory.deleted_at.is_(None),
        or_(Memory.title.like(like), Memory.raw_content.like(like)),
    ).limit(limit).all():
        results.append({"type": "memory", "id": m.id, "title": m.title or "无标题",
                        "snippet": (m.raw_content or "")[:100], "href": "/memories"})

    for s in db.query(Story).filter(
        Story.user_id == user.id, Story.deleted_at.is_(None),
        or_(Story.title.like(like), Story.summary.like(like)),
    ).limit(limit).all():
        results.append({"type": "story", "id": s.id, "title": s.title or "无标题",
                        "snippet": (s.summary or "")[:100], "href": "/story?tab=stories"})

    for p in db.query(Person).filter(
        Person.user_id == user.id, Person.deleted_at.is_(None), Person.name.like(like),
    ).limit(limit).all():
        results.append({"type": "person", "id": p.id, "title": p.name,
                        "snippet": (p.notes or "")[:100], "href": "/graph"})

    for a in db.query(MediaAsset).filter(
        MediaAsset.user_id == user.id, MediaAsset.deleted_at.is_(None),
        or_(MediaAsset.original_filename.like(like), MediaAsset.caption.like(like)),
    ).limit(limit).all():
        results.append({"type": "media", "id": a.id, "title": a.original_filename or "媒体",
                        "snippet": (a.caption or "")[:100], "href": "/media"})

    return {"query": q, "results": results[: limit * 2]}
