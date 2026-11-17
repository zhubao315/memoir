"""Common columns / mixins for domain tables."""

import uuid

from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func


def new_id() -> str:
    return str(uuid.uuid4())


class UUIDMixin:
    id = Column(String, primary_key=True, default=new_id)


class TimestampMixin:
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class SoftDeleteMixin:
    deleted_at = Column(DateTime, nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
