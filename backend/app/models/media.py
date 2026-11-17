"""Media assets, recordings, transcripts (原则 A: raw content immutable)."""

from sqlalchemy import Boolean, Column, Float, Index, Integer, JSON, String, Text

from app.db.base import Base
from app.models.common import SoftDeleteMixin, TimestampMixin, UUIDMixin


class MediaAsset(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "media_assets"
    # 列表与按记忆聚合都先按 user_id / deleted_at 过滤，复合索引覆盖这些热路径。
    __table_args__ = (
        Index("ix_media_assets_user_deleted_created", "user_id", "deleted_at", "created_at"),
        Index("ix_media_assets_user_memory", "user_id", "memory_id"),
    )
    user_id = Column(String, nullable=False, index=True)
    family_id = Column(String, nullable=True, index=True)
    memory_id = Column(String, nullable=True, index=True)
    storage_key = Column(String, nullable=False)  # resolved by storage adapter
    storage_backend = Column(String, default="local")
    original_filename = Column(String, nullable=True)
    media_type = Column(String, nullable=False)  # photo|video|audio|document
    mime_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    sha256 = Column(String, nullable=True)
    caption = Column(Text, nullable=True)          # 用户可编辑的说明文字
    # 以下为 AI 衍生内容，可重算，不得覆盖 storage_key / sha256 等原始事实。
    ocr_text = Column(Text, nullable=True)
    ai_description = Column(Text, nullable=True)
    taken_at = Column(String, nullable=True)
    legacy_media_id = Column(String, nullable=True, index=True)


class Recording(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "recordings"
    __table_args__ = (
        Index("ix_recordings_user_media", "user_id", "media_asset_id"),
    )
    user_id = Column(String, nullable=False, index=True)
    family_id = Column(String, nullable=True, index=True)
    media_asset_id = Column(String, nullable=True, index=True)
    interview_id = Column(String, nullable=True, index=True)
    prompt_id = Column(String, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    mime_type = Column(String, nullable=True)
    status = Column(String, default="uploaded")  # uploaded|transcribing|transcribed|failed
    error = Column(Text, nullable=True)
    # 原始录音永久保留；无 update 接口，只有软删除且受限。


class Transcript(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "transcripts"
    __table_args__ = (
        Index("ix_transcripts_user_recording", "user_id", "recording_id"),
    )
    recording_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    language = Column(String, nullable=True)
    is_corrected = Column(Boolean, default=False)
    engine = Column(String, nullable=True)
    raw_response = Column(JSON, nullable=True)
