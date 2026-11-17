"""Backward-compatible v0.1 REST API (mounted at /api).

All original endpoints keep their paths and response shapes. The only addition is
GET /api/media/{id}/file, which fixes the originally broken media-viewing feature.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.ratelimit import check_rate_limit, client_key
from app.core.security import verify_password
from app.models.legacy_tables import Entry, Media, Tag, User
from app.services import auth as auth_service

router = APIRouter(tags=["legacy-v0.1"])


# ---------- schemas (same shapes as v0.1) ----------
class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class EntryCreate(BaseModel):
    title: str
    content: Optional[str] = None
    entry_date: str
    entry_type: Optional[str] = "memory"
    mood: Optional[str] = "neutral"
    location: Optional[dict] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = False


class EntryUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    entry_date: Optional[str] = None
    entry_type: Optional[str] = None
    mood: Optional[str] = None
    location: Optional[dict] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None


class EntryResponse(BaseModel):
    id: str
    user_id: str
    title: str
    content: Optional[str]
    entry_date: str
    entry_type: str
    mood: str
    location: Optional[dict]
    tags: List[str]
    is_public: bool
    created_at: datetime
    updated_at: datetime
    media_count: int = 0

    class Config:
        from_attributes = True


class MediaResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    caption: Optional[str]
    taken_at: Optional[datetime]

    class Config:
        from_attributes = True


class TagCreate(BaseModel):
    name: str
    color: Optional[str] = "#6366f1"
    icon: Optional[str] = None


class TagResponse(BaseModel):
    id: str
    name: str
    color: str
    icon: Optional[str]

    class Config:
        from_attributes = True


# ---------- auth ----------
@router.post("/api/auth/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    return auth_service.register(db, user.username, user.email, user.password)


@router.post("/api/auth/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    tokens = auth_service.login(db, user.username, user.password)
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
        # Explicit serialization: without a response_model, FastAPI's encoder
        # would emit {} for a SQLAlchemy model instance.
        "user": UserResponse.model_validate(tokens["user"]).model_dump(mode="json"),
    }


@router.get("/api/auth/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


# ---------- entries ----------
def _with_media_count(db: Session, entry: Entry) -> EntryResponse:
    entry.media_count = db.query(Media).filter(Media.entry_id == entry.id).count()
    return EntryResponse.model_validate(entry)


@router.get("/api/entries", response_model=List[EntryResponse])
def get_entries(
    skip: int = 0,
    limit: int = 50,
    entry_type: Optional[str] = None,
    mood: Optional[str] = None,
    tag: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Entry).filter(Entry.user_id == current_user.id)
    if entry_type:
        q = q.filter(Entry.entry_type == entry_type)
    if mood:
        q = q.filter(Entry.mood == mood)
    if tag:
        # legacy JSON column; filter on exact array membership via contains as before,
        # but also support the richer v1 /api/v1/memories for reliable tag filtering.
        q = q.filter(Entry.tags.contains(tag))
    entries = q.order_by(Entry.entry_date.desc()).offset(skip).limit(limit).all()
    return [_with_media_count(db, e) for e in entries]


@router.get("/api/entries/{entry_id}", response_model=EntryResponse)
def get_entry(entry_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.id == entry_id, Entry.user_id == current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="记忆条目不存在")
    return _with_media_count(db, entry)


@router.post("/api/entries", response_model=EntryResponse)
def create_entry(entry: EntryCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_entry = Entry(
        user_id=current_user.id,
        title=entry.title,
        content=entry.content,
        entry_date=entry.entry_date,
        entry_type=entry.entry_type or "memory",
        mood=entry.mood or "neutral",
        location=entry.location or {},
        tags=entry.tags or [],
        is_public=bool(entry.is_public),
    )
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return _with_media_count(db, db_entry)


@router.put("/api/entries/{entry_id}", response_model=EntryResponse)
def update_entry(entry_id: str, entry: EntryUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_entry = db.query(Entry).filter(Entry.id == entry_id, Entry.user_id == current_user.id).first()
    if not db_entry:
        raise HTTPException(status_code=404, detail="记忆条目不存在")
    for field in ("title", "content", "entry_date", "entry_type", "mood", "location", "tags", "is_public"):
        value = getattr(entry, field)
        if value is not None:
            setattr(db_entry, field, value)
    db.commit()
    db.refresh(db_entry)
    return _with_media_count(db, db_entry)


@router.delete("/api/entries/{entry_id}")
def delete_entry(entry_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.id == entry_id, Entry.user_id == current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="记忆条目不存在")
    db.query(Media).filter(Media.entry_id == entry_id).delete()
    db.delete(entry)
    db.commit()
    return {"message": "删除成功"}


# ---------- media ----------
@router.post("/api/entries/{entry_id}/media", response_model=MediaResponse)
async def upload_media(
    entry_id: str,
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from pathlib import Path

    from app.services.media import persist_asset, read_upload, validate_upload

    entry = db.query(Entry).filter(Entry.id == entry_id, Entry.user_id == current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="记忆条目不存在")
    data = await read_upload(file)
    mime, media_type = validate_upload(file.filename or "file", data, file.content_type)
    asset = persist_asset(db, current_user.id, data, file.filename or "file", mime, media_type)
    file_type = {"photo": "photo", "video": "video", "audio": "audio"}.get(media_type, "photo")
    db_media = Media(
        entry_id=entry_id,
        user_id=current_user.id,
        filename=file.filename or "file",
        file_type=file_type,
        file_path=asset.storage_key,
        file_size=len(data),
        mime_type=mime,
        caption=caption,
    )
    db.add(db_media)
    db.commit()
    db.refresh(db_media)
    return db_media


@router.get("/api/entries/{entry_id}/media", response_model=List[MediaResponse])
def get_media(entry_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.id == entry_id, Entry.user_id == current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="记忆条目不存在")
    return db.query(Media).filter(Media.entry_id == entry_id).all()


@router.delete("/api/media/{media_id}")
def delete_media(media_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.storage import get_storage

    media = db.query(Media).filter(Media.id == media_id, Media.user_id == current_user.id).first()
    if not media:
        raise HTTPException(status_code=404, detail="媒体文件不存在")
    try:
        get_storage().delete(media.file_path)
    except Exception:
        pass
    db.delete(media)
    db.commit()
    return {"message": "删除成功"}


@router.get("/api/media/{media_id}/file")
def get_media_file(media_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """FIX: originally missing endpoint. Ownership checked; streams the authorized file."""
    from fastapi.responses import Response

    from app.storage import get_storage

    media = db.query(Media).filter(Media.id == media_id, Media.user_id == current_user.id).first()
    if not media:
        raise HTTPException(status_code=404, detail="媒体文件不存在")
    try:
        data = get_storage().read(media.file_path)
    except Exception:
        raise HTTPException(status_code=404, detail="文件不存在")
    return Response(content=data, media_type=media.mime_type or "application/octet-stream")


# ---------- tags ----------
@router.get("/api/tags", response_model=List[TagResponse])
def get_tags(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Tag).filter(Tag.user_id == current_user.id).all()


@router.post("/api/tags", response_model=TagResponse)
def create_tag(tag: TagCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.query(Tag).filter(Tag.user_id == current_user.id, Tag.name == tag.name).first():
        raise HTTPException(status_code=400, detail="标签已存在")
    db_tag = Tag(user_id=current_user.id, name=tag.name, color=tag.color or "#6366f1", icon=tag.icon)
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag


@router.delete("/api/tags/{tag_id}")
def delete_tag(tag_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tag = db.query(Tag).filter(Tag.id == tag_id, Tag.user_id == current_user.id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    for entry in db.query(Entry).filter(Entry.user_id == current_user.id).all():
        if entry.tags and tag.name in entry.tags:
            entry.tags.remove(tag.name)
    db.delete(tag)
    db.commit()
    return {"message": "删除成功"}


# ---------- stats ----------
@router.get("/api/stats")
def get_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_entries = db.query(Entry).filter(Entry.user_id == current_user.id).count()
    total_media = db.query(Media).filter(Media.user_id == current_user.id).count()
    total_tags = db.query(Tag).filter(Tag.user_id == current_user.id).count()
    entry_types = db.query(Entry.entry_type, func.count(Entry.id)).filter(Entry.user_id == current_user.id).group_by(Entry.entry_type).all()
    moods = db.query(Entry.mood, func.count(Entry.id)).filter(Entry.user_id == current_user.id).group_by(Entry.mood).all()
    recent = db.query(Entry).filter(
        Entry.user_id == current_user.id,
        Entry.created_at >= datetime.utcnow() - timedelta(days=7),
    ).count()
    return {
        "total_entries": total_entries,
        "total_media": total_media,
        "total_tags": total_tags,
        "entry_types": {r[0]: r[1] for r in entry_types},
        "moods": {r[0]: r[1] for r in moods},
        "recent_entries": recent,
    }
