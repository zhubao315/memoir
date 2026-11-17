"""Legacy Book: books, chapters, QR codes, export jobs."""

from sqlalchemy import Column, Integer, JSON, String, Text

from app.db.base import Base
from app.models.common import SoftDeleteMixin, TimestampMixin, UUIDMixin


class Book(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "books"
    user_id = Column(String, nullable=False, index=True)
    family_id = Column(String, nullable=True, index=True)
    title = Column(String, nullable=False)
    subtitle = Column(String, nullable=True)
    author = Column(String, nullable=True)
    cover_media_id = Column(String, nullable=True)
    template = Column(String, default="classic")
    status = Column(String, default="draft")  # draft|ready|exported
    settings = Column(JSON, nullable=True)


class BookChapter(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "book_chapters"
    book_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    intro = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    cover_media_id = Column(String, nullable=True)
    story_ids = Column(JSON, nullable=True)
    media_ids = Column(JSON, nullable=True)
    order_index = Column(Integer, default=0)


class BookQRCode(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "book_qr_codes"
    book_id = Column(String, nullable=True, index=True)
    story_id = Column(String, nullable=True, index=True)
    chapter_id = Column(String, nullable=True, index=True)
    token = Column(String, nullable=False, unique=True, index=True)  # stable, unpredictable
    target_url = Column(String, nullable=True)
    status = Column(String, default="active")  # active|revoked
    revoked_at = Column(String, nullable=True)


class BookExportJob(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "book_export_jobs"
    book_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    format = Column(String, nullable=False)  # pdf|markdown|json|epub
    status = Column(String, default="pending")
    file_path = Column(String, nullable=True)
    error = Column(Text, nullable=True)
