"""Audit log viewer — only the current user's own actions (privacy by design)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.identity import AuditLog

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("")
def activity(limit: int = 50, user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(AuditLog).filter(AuditLog.user_id == user.id).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "action": r.action,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "detail": r.detail,
            "created_at": r.created_at,
        }
        for r in rows
    ]
