"""Family collaboration: comments, reactions, votes, share tokens."""

from sqlalchemy import Column, Integer, String, Text

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDMixin


class Comment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "comments"
    user_id = Column(String, nullable=False, index=True)
    family_id = Column(String, nullable=True, index=True)
    resource_type = Column(String, nullable=False)  # story|memory|book
    resource_id = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    parent_id = Column(String, nullable=True)


class Reaction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reactions"
    user_id = Column(String, nullable=False, index=True)
    resource_type = Column(String, nullable=False)
    resource_id = Column(String, nullable=False, index=True)
    kind = Column(String, default="heart")  # heart|like|remember


class Vote(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "votes"
    user_id = Column(String, nullable=False, index=True)
    family_id = Column(String, nullable=True, index=True)
    prompt_id = Column(String, nullable=False, index=True)
    value = Column(Integer, default=1)


class ShareToken(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "share_tokens"
    resource_type = Column(String, nullable=False)  # story|book|qr
    resource_id = Column(String, nullable=False, index=True)
    token = Column(String, nullable=False, unique=True, index=True)  # unpredictable public token
    created_by = Column(String, nullable=False)
    expires_at = Column(String, nullable=True)
    revoked_at = Column(String, nullable=True)
    permissions = Column(String, default="read")  # read|listen
