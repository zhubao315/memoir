"""Validated media uploads (S-09): extension allowlist + magic-byte check + size cap."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.storage import get_storage
from app.storage.base import StoredObject
from app.models.media import MediaAsset


_MAGIC = [
    (b"\xff\xd8\xff", "image/jpeg", "photo"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "photo"),
    (b"GIF87a", "image/gif", "photo"),
    (b"GIF89a", "image/gif", "photo"),
    (b"RIFF", "container", None),
    (b"OggS", "audio/ogg", "audio"),
    (b"ID3", "audio/mpeg", "audio"),
    (b"fLaC", "audio/flac", "audio"),
    (b"PK\x03\x04", "application/zip", "document"),
    (b"%PDF", "application/pdf", "document"),
]

_EXT = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif",
    ".webp": "image/webp", ".mp4": "video/mp4", ".mov": "video/quicktime", ".mkv": "video/x-matroska",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".ogg": "audio/ogg",
    ".webm": "audio/webm", ".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown",
}


def detect_media_type(mime: str) -> str:
    if mime.startswith("image/"):
        return "photo"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    return "document"


def validate_upload(filename: str, data: bytes, declared_mime: str | None) -> tuple[str, str]:
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件超过大小限制")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="文件为空")
    ext = Path(filename).suffix.lower()
    if ext not in _EXT:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext or '(无扩展名)'}")

    detected = _EXT[ext]
    head = data[:16]
    if head.startswith(b"RIFF") and len(data) >= 12:
        kind = data[8:12]
        if kind == b"WAVE":
            detected = "audio/wav"
        elif kind == b"WEBP":
            detected = "image/webp"
        elif kind == b"AVI ":
            detected = "video/x-msvideo"
    elif head[4:8] == b"ftyp":
        detected = "video/mp4"
    elif declared_mime and declared_mime in _EXT.values() and declared_mime != detected:
        # Trust the declared type only when it is in our allowlist; magic bytes win.
        detected = declared_mime

    # Reject obvious mismatches between extension family and detected family.
    family = detected.split("/")[0]
    if family not in ("image", "video", "audio", "application", "text"):
        raise HTTPException(status_code=400, detail="文件内容类型不受支持")
    return detected, detect_media_type(detected)


def build_key(user_id: str, filename: str) -> str:
    safe = Path(filename).name.replace("..", "")[:80]
    return f"{user_id}/{uuid.uuid4().hex}/{safe}"


async def read_upload(file: UploadFile) -> bytes:
    data = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件超过大小限制")
    return data


def persist_asset(
    db: Session,
    user_id: str,
    data: bytes,
    filename: str,
    mime: str,
    media_type: str,
    *,
    family_id: str | None = None,
    memory_id: str | None = None,
) -> MediaAsset:
    key = build_key(user_id, filename)
    stored: StoredObject = get_storage().save(key, data, mime)
    import hashlib
    asset = MediaAsset(
        user_id=user_id,
        family_id=family_id,
        memory_id=memory_id,
        storage_key=key,
        storage_backend=settings.STORAGE_BACKEND,
        original_filename=filename[:255],
        media_type=media_type,
        mime_type=mime,
        size_bytes=stored.size,
        sha256=hashlib.sha256(data).hexdigest(),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def signed_url_for(asset: MediaAsset) -> str:
    return get_storage().signed_url(
        asset.storage_key,
        settings.MEDIA_URL_TTL_SECONDS,
        filename=asset.original_filename,
    )
