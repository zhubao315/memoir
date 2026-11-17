"""Media Asset endpoints with private storage + short-lived signed URLs."""

from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.media import MediaAsset, Recording
from app.services.media import (
    persist_asset,
    read_upload,
    signed_url_for,
    validate_upload,
)
from app.storage import get_storage

router = APIRouter(prefix="/media", tags=["media"])


class MediaOut(BaseModel):
    id: str
    storage_key: str
    media_type: str
    mime_type: str | None
    size_bytes: int | None
    original_filename: str | None
    url: str = ""

    class Config:
        from_attributes = True


class MediaListItem(MediaOut):
    caption: str | None = None
    created_at: datetime | None = None


class UrlOut(BaseModel):
    url: str
    expires_in: int


@router.get("", response_model=List[MediaListItem])
def list_media(
    media_type: str | None = None,
    limit: int = 200,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the current user's media assets with short-lived signed URLs.

    media_type supports comma-separated values, e.g. 'audio,video'.
    """
    q = db.query(MediaAsset).filter(MediaAsset.user_id == user.id, MediaAsset.deleted_at.is_(None))
    if media_type:
        types = [t.strip() for t in media_type.split(",") if t.strip()]
        if types:
            q = q.filter(MediaAsset.media_type.in_(types))
    rows = q.order_by(MediaAsset.created_at.desc()).limit(limit).all()
    out = []
    for a in rows:
        item = MediaListItem.model_validate(a)
        item.url = signed_url_for(a)
        item.created_at = str(a.created_at) if a.created_at else None
        out.append(item)
    return out


@router.get("/file")
def serve_signed_file(token: str):
    """Stream a file through a short-lived signed URL (no auth header needed).

    Declared before /{asset_id} so the static path is not shadowed by the dynamic one.
    """
    try:
        payload = get_storage().resolve_signed_token(token, max_age=settings.MEDIA_URL_TTL_SECONDS) if hasattr(get_storage(), "resolve_signed_token") else None
    except Exception:
        payload = None
    if payload is None:
        raise HTTPException(status_code=400, detail="当前存储后端不使用本地签名端点")
    from pathlib import Path

    key = payload.get("key", "")
    try:
        data = get_storage().read(key)
    except Exception:
        raise HTTPException(status_code=404, detail="文件不存在")
    filename = payload.get("f") or Path(key).name
    headers = {"Content-Disposition": f'inline; filename="{filename}"'}
    return Response(content=data, media_type="application/octet-stream", headers=headers)


@router.post("/upload", response_model=MediaOut, status_code=201)
async def upload(
    file: UploadFile = File(...),
    memory_id: str | None = Form(None),
    family_id: str | None = Form(None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = await read_upload(file)
    mime, media_type = validate_upload(file.filename or "file", data, file.content_type)
    asset = persist_asset(db, user.id, data, file.filename or "file", mime, media_type, family_id=family_id, memory_id=memory_id)
    out = MediaOut.model_validate(asset)
    out.url = signed_url_for(asset)
    return out


@router.get("/{asset_id}/url", response_model=UrlOut)
def get_url(asset_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    asset = db.query(MediaAsset).filter(MediaAsset.id == asset_id, MediaAsset.user_id == user.id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="媒体不存在")
    return {"url": signed_url_for(asset), "expires_in": settings.MEDIA_URL_TTL_SECONDS}


@router.get("/{asset_id}", response_model=MediaOut)
def get_asset(asset_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    asset = db.query(MediaAsset).filter(MediaAsset.id == asset_id, MediaAsset.user_id == user.id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="媒体不存在")
    out = MediaOut.model_validate(asset)
    out.url = signed_url_for(asset)
    return out


@router.delete("/{asset_id}")
def delete_asset(asset_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    asset = db.query(MediaAsset).filter(MediaAsset.id == asset_id, MediaAsset.user_id == user.id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="媒体不存在")
    # 原始录音不能被普通协作者删除；此处仅资产所有者可操作，且录音另受保护。
    linked_recording = db.query(Recording).filter(Recording.media_asset_id == asset_id).first()
    if linked_recording:
        raise HTTPException(status_code=403, detail="原始录音受保护，不能通过此接口删除")
    get_storage().delete(asset.storage_key)
    db.delete(asset)
    db.commit()
    return {"message": "删除成功"}



