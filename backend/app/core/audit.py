"""Audit logging helper (S-11)."""

from __future__ import annotations

from fastapi import Request

from app.core.security import utcnow
from app.db.session import SessionLocal
from app.models.identity import AuditLog


def log_action(
    action: str,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: str | None = None,
    request: Request | None = None,
) -> None:
    try:
        db = SessionLocal()
        try:
            db.add(
                AuditLog(
                    user_id=user_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    detail=detail,
                    ip=request.client.host if request and request.client else None,
                    created_at=utcnow(),
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        # Auditing must never break the primary operation.
        pass
