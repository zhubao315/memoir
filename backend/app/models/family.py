"""Family spaces, memberships, invitations (P1: Family Circle)."""

from sqlalchemy import Column, DateTime, String, Text

from app.db.base import Base
from app.models.common import SoftDeleteMixin, TimestampMixin, UUIDMixin


class Family(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "families"
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(String, nullable=False, index=True)
    avatar_url = Column(String, nullable=True)


class FamilyMember(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "family_members"
    family_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    role = Column(String, default="collaborator", nullable=False)
    # owner | admin | storyteller | collaborator | viewer
    display_name = Column(String, nullable=True)
    invited_by = Column(String, nullable=True)
    joined_at = Column(DateTime, nullable=True)


class FamilyInvitation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "family_invitations"
    family_id = Column(String, nullable=False, index=True)
    email = Column(String, nullable=False, index=True)
    role = Column(String, default="collaborator")
    token = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, default="pending")  # pending|accepted|expired|revoked
    expires_at = Column(DateTime, nullable=False)
    invited_by = Column(String, nullable=False)
