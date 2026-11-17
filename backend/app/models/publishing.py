"""Legacy Book：书籍、章节、二维码与导出任务。

归属与隔离约定（详见 docs/architecture/DATA_MODEL_FAMILY_LEGACY.md）：
- Book.user_id 为唯一所有者；书籍/章节修改必须服务端校验该归属。
- BookQRCode.token 为稳定且不可预测的公开令牌，状态机 active → revoked；
  公开故事页只暴露 token，不暴露 storage_key / file_path 等内部路径。
- 二维码可由此生成，撤销即时生效（public_story 校验 status == active）。
"""

from sqlalchemy import Column, Integer, JSON, String, Text

from app.db.base import Base
from app.models.common import SoftDeleteMixin, TimestampMixin, UUIDMixin


class Book(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """回忆录；user_id 为所有者，可选 family_id 表示归属家庭空间。"""

    __tablename__ = "books"
    user_id = Column(String, nullable=False, index=True)
    family_id = Column(String, nullable=True, index=True)
    title = Column(String, nullable=False)
    subtitle = Column(String, nullable=True)
    author = Column(String, nullable=True)
    cover_media_id = Column(String, nullable=True)  # 封面媒体 ID（不直接存路径）
    template = Column(String, default="classic")
    status = Column(String, default="draft")  # draft|ready|exported
    settings = Column(JSON, nullable=True)  # 如 back_cover_media_id（封底）


class BookChapter(UUIDMixin, TimestampMixin, Base):
    """章节；order_index 用于上移/下移排序（PUT /chapters/{id}）。"""

    __tablename__ = "book_chapters"
    book_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    intro = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    cover_media_id = Column(String, nullable=True)
    story_ids = Column(JSON, nullable=True)  # 引用本人故事 ID
    media_ids = Column(JSON, nullable=True)  # 引用本人媒体 ID
    order_index = Column(Integer, default=0)


class BookQRCode(UUIDMixin, TimestampMixin, Base):
    """故事公开二维码；状态机 active → revoked，撤销后公开页立即 404。"""

    __tablename__ = "book_qr_codes"
    book_id = Column(String, nullable=True, index=True)
    story_id = Column(String, nullable=True, index=True)
    chapter_id = Column(String, nullable=True, index=True)
    token = Column(String, nullable=False, unique=True, index=True)  # stable, unpredictable
    target_url = Column(String, nullable=True)  # 仅内部构造，不在响应中暴露
    status = Column(String, default="active")  # active|revoked
    revoked_at = Column(String, nullable=True)


class BookExportJob(UUIDMixin, TimestampMixin, Base):
    """导出任务；file_path 为内部路径，仅用于服务端读取，不返回给前端。"""

    __tablename__ = "book_export_jobs"
    book_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    format = Column(String, nullable=False)  # pdf|markdown|json|epub
    status = Column(String, default="pending")  # pending|completed|failed
    file_path = Column(String, nullable=True)
    error = Column(Text, nullable=True)
