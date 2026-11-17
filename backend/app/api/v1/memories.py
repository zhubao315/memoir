"""Memory Vault endpoints (v1)."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.deps import get_current_user, get_db
from app.models.memory import Memory
from app.models.media import MediaAsset
from app.schemas.memory import MemoryIn, MemoryOut, MemoryUpdate
from app.services.media import signed_url_for
from app.services.tasks import create_job, enqueue

router = APIRouter(prefix="/memories", tags=["memory-vault"])


class MemoryMediaOut(BaseModel):
    id: str
    media_type: str
    caption: str | None = None
    url: str

    class Config:
        from_attributes = True


@router.get("/{memory_id}/media", response_model=List[MemoryMediaOut])
def memory_media(memory_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Media attached to a memory, with short-lived signed URLs (原则: 私有存储)."""
    memory = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user.id, Memory.deleted_at.is_(None)).first()
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    assets = db.query(MediaAsset).filter(
        MediaAsset.memory_id == memory_id,
        MediaAsset.user_id == user.id,
        MediaAsset.deleted_at.is_(None),
    ).order_by(MediaAsset.created_at.asc()).all()
    return [
        MemoryMediaOut(
            id=a.id,
            media_type=a.media_type,
            caption=a.caption,
            url=signed_url_for(a),
        )
        for a in assets
    ]


@router.get("", response_model=List[MemoryOut])
def list_memories(
    skip: int = 0,
    limit: int = 50,
    memory_type: str | None = None,
    mood: str | None = None,
    tag: str | None = None,
    search: str | None = None,
    show_trash: bool = False,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Memory).filter(
        Memory.user_id == user.id,
        Memory.deleted_at.isnot(None) if show_trash else Memory.deleted_at.is_(None),
    )
    if memory_type:
        q = q.filter(Memory.memory_type == memory_type)
    if mood:
        q = q.filter(Memory.mood == mood)
    if search:
        q = q.filter(Memory.raw_content.contains(search) | Memory.title.contains(search))
    rows = q.order_by(Memory.created_at.desc()).offset(skip).limit(limit).all()
    if tag:
        rows = [r for r in rows if tag in (r.tags or [])]
    return rows


@router.post("", response_model=MemoryOut, status_code=201)
def create_memory(payload: MemoryIn, background: BackgroundTasks, user=Depends(get_current_user), db: Session = Depends(get_db)):
    m = Memory(
        user_id=user.id,
        creator_id=user.id,
        family_id=payload.family_id,
        source=payload.source,
        title=payload.title,
        raw_content=payload.raw_content,
        occurred_at=payload.occurred_at,
        memory_type=payload.memory_type,
        mood=payload.mood,
        location=payload.location,
        tags=payload.tags or [],
        visibility=payload.visibility,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    # Async extraction + embedding jobs.
    job = create_job(db, user.id, "memory_extraction", {"memory_id": m.id})
    enqueue(background, job.id)
    job2 = create_job(db, user.id, "embedding", {"resource_type": "memory", "resource_id": m.id, "family_id": payload.family_id})
    enqueue(background, job2.id)
    return m


@router.get("/{memory_id}", response_model=MemoryOut)
def get_memory(memory_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user.id, Memory.deleted_at.is_(None)).first()
    if not m:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return m


@router.put("/{memory_id}", response_model=MemoryOut)
def update_memory(memory_id: str, payload: MemoryUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user.id, Memory.deleted_at.is_(None)).first()
    if not m:
        raise HTTPException(status_code=404, detail="记忆不存在")
    for field in payload.model_fields_set:
        setattr(m, field, getattr(payload, field))
    db.commit()
    db.refresh(m)
    log_action("memory.update", user_id=user.id, resource_type="memory", resource_id=m.id)
    return m


@router.post("/{memory_id}/restore", response_model=MemoryOut)
def restore_memory(memory_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user.id, Memory.deleted_at.isnot(None)).first()
    if not m:
        raise HTTPException(status_code=404, detail="回收站中没有该记忆")
    m.deleted_at = None
    db.commit()
    db.refresh(m)
    log_action("memory.restore", user_id=user.id, resource_type="memory", resource_id=m.id)
    return m


@router.delete("/{memory_id}/purge")
def purge_memory(memory_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user.id, Memory.deleted_at.isnot(None)).first()
    if not m:
        raise HTTPException(status_code=404, detail="回收站中没有该记忆")
    db.query(MediaAsset).filter(MediaAsset.memory_id == m.id).delete()
    db.delete(m)
    db.commit()
    log_action("memory.purge", user_id=user.id, resource_type="memory", resource_id=m.id)
    return {"message": "已彻底删除"}


@router.delete("/{memory_id}")
def delete_memory(memory_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user.id, Memory.deleted_at.is_(None)).first()
    if not m:
        raise HTTPException(status_code=404, detail="记忆不存在")
    from app.core.security import utcnow

    m.deleted_at = utcnow()  # soft delete
    db.commit()
    log_action("memory.soft_delete", user_id=user.id, resource_type="memory", resource_id=m.id)
    return {"message": "已移入回收站"}
