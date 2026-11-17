"""Identity, sessions, token revocation, audit & data-subject requests."""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.db.base import Base
from app.models.common import SoftDeleteMixin, TimestampMixin, UUIDMixin


class Session(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sessions"
    user_id = Column(String, nullable=False, index=True)
    refresh_token_hash = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    user_agent = Column(String, nullable=True)
    ip = Column(String, nullable=True)


class RefreshToken(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "refresh_tokens"
    user_id = Column(String, nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    jti = Column(String, nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    replaced_by = Column(String, nullable=True)


class TokenDenylist(Base):
    __tablename__ = "token_denylist"
    token_hash = Column(String, primary_key=True)  # sha256 of raw token
    jti = Column(String, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)


class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"
    user_id = Column(String, nullable=True, index=True)
    action = Column(String, nullable=False, index=True)
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    detail = Column(Text, nullable=True)
    ip = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)


class DataExportJob(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "data_export_jobs"
    user_id = Column(String, nullable=False, index=True)
    status = Column(String, default="pending")
    file_path = Column(String, nullable=True)
    error = Column(Text, nullable=True)


class DeletionRequest(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "deletion_requests"
    user_id = Column(String, nullable=False, index=True)
    status = Column(String, default="pending")
    scheduled_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
