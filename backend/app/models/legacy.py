"""Digital Legacy: contacts, explicit policies, events (no automatic handover)."""

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDMixin


class LegacyContact(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "legacy_contacts"
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    relationship = Column(String, nullable=True)
    identity_verified = Column(Integer, default=0)
    verification_method = Column(String, nullable=True)


class LegacyPolicy(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "legacy_policies"
    user_id = Column(String, nullable=False, index=True)
    contact_id = Column(String, nullable=False, index=True)
    granted = Column(Integer, default=0)  # 必须显式授权
    granted_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    trigger = Column(String, default="manual")  # manual|scheduled
    release_after_days = Column(Integer, nullable=True)
    release_at = Column(DateTime, nullable=True)
    share_scope = Column(JSON, nullable=True)  # 仅指定的 story/memory id 列表
    conditions = Column(JSON, nullable=True)
    status = Column(String, default="draft")  # draft|active|disputed|revoked|released


class LegacyEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "legacy_events"
    policy_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)  # granted|revoked|triggered|verified|disputed|released
    actor_id = Column(String, nullable=True)
    detail = Column(Text, nullable=True)
