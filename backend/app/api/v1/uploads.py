"""Chunked / resumable large-file upload for photos, audio and video.

Protocol:
1) POST /uploads/init  {filename, size, mime_type, memory_id?} -> {upload_id, chunk_size, received[]}
2) PUT  /uploads/{id}/chunk?index=N  (binary)  -> {received:[...], next_index}
3) POST /uploads/{id}/complete -> MediaAsset + signed URL
Chunks live under the user's own directory keyed by upload id (逻辑隔离)。
"""

from __future__ import annotations

import secrets
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.security import utcnow
from app.models.memory import Memory
from app.models.media import MediaAsset
from app.services.media import detect_media_type, signed_url_for, validate_upload
from app.storage import get_storage

router = APIRouter(prefix="/uploads", tags=["uploads"])
CHUNK_SIZE = 2 * 1024 * 1024  # 2 MiB

META: dict[str, dict] = {}  # in-memory upload session store; swap for Redis in prod


class InitIn(BaseModel):
    filename: str
    size: int
    mime_type: str | None = None
    memory_id: str | None = None
    family_id: str | None = None


def _dir(user_id: str, upload_id: str) -> Path:
    p = settings.upload_dir / "_chunks" / user_id / upload_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _session(upload_id: str, user_id: str) -> dict:
    s = META.get(upload_id)
    if not s or s["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="上传会话不存在")
    return s


@router.post("/init")
def init(payload: InitIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.size <= 0 or payload.size > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件大小不合法或超过上限")
    if payload.memory_id:
        m = db.query(Memory).filter(Memory.id == payload.memory_id, Memory.user_id == user.id, Memory.deleted_at.is_(None)).first()
        if not m:
            raise HTTPException(status_code=404, detail="目标记忆不存在")
    uid = secrets.token_urlsafe(18)
    META[uid] = {
        "user_id": user.id,
        "filename": payload.filename,
        "size": payload.size,
        "mime_type": payload.mime_type,
        "memory_id": payload.memory_id,
        "family_id": payload.family_id,
        "created_at": utcnow().isoformat(),
        "received": [],
    }
    total = (payload.size + CHUNK_SIZE - 1) // CHUNK_SIZE
    return {"upload_id": uid, "chunk_size": CHUNK_SIZE, "total_chunks": total, "received": []}


@router.put("/{upload_id}/chunk")
async def chunk(upload_id: str, index: int, request: Request, user=Depends(get_current_user)):
    s = _session(upload_id, user.id)
    if index < 0 or index * CHUNK_SIZE >= s["size"]:
        raise HTTPException(status_code=400, detail="分片序号越界")
    data = await request.body()
    path = _dir(user.id, upload_id) / f"{index:06d}.part"
    path.write_bytes(data)
    if index not in s["received"]:
        s["received"].append(index)
        s["received"].sort()
    return {"received": s["received"], "next_index": (max(s["received"]) + 1) if s["received"] else 0}


@router.post("/{upload_id}/complete")
def complete(upload_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    s = _session(upload_id, user.id)
    folder = _dir(user.id, upload_id)
    parts = sorted(folder.glob("*.part"))
    data = b"".join(p.read_bytes() for p in parts)
    if len(data) != s["size"]:
        raise HTTPException(status_code=400, detail=f"分片不完整：期望 {s['size']} 字节，实际 {len(data)}")
    mime, media_type = validate_upload(s["filename"], data, s["mime_type"])
    key = f"{user.id}/{uuid.uuid4().hex}/{Path(s['filename']).name}"
    stored = get_storage().save(key, data, mime)
    import hashlib
    asset = MediaAsset(
        user_id=user.id, family_id=s.get("family_id"), memory_id=s.get("memory_id"),
        storage_key=key, storage_backend=settings.STORAGE_BACKEND,
        original_filename=s["filename"][:255], media_type=media_type, mime_type=mime,
        size_bytes=stored.size, sha256=hashlib.sha256(data).hexdigest(),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    for p in parts:
        p.unlink()
    try:
        folder.rmdir()
    except OSError:
        pass
    META.pop(upload_id, None)
    out = {"id": asset.id, "media_type": media_type, "mime_type": mime,
           "size_bytes": asset.size_bytes, "original_filename": asset.original_filename,
           "url": signed_url_for(asset)}
    return out
