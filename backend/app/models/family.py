"""家庭空间、成员与邀请（Family Circle）。

归属与隔离约定（详见 docs/architecture/DATA_MODEL_FAMILY_LEGACY.md）：
- 每个家庭可独立存在；成员通过 FamilyMember 关联到 user_id，多家庭互不串号。
- 角色：owner | admin | storyteller | collaborator | viewer（等级依次递减）。
- 邀请 token：唯一且不可预测，带 expires_at；状态机 pending → accepted / expired / revoked。
"""

from sqlalchemy import Column, DateTime, String, Text

from app.db.base import Base
from app.models.common import SoftDeleteMixin, TimestampMixin, UUIDMixin


class Family(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """家庭空间；owner_id 为创建者（所有者）。软删除保留归属痕迹。"""

    __tablename__ = "families"
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(String, nullable=False, index=True)  # 归属：用户 ID
    avatar_url = Column(String, nullable=True)


class FamilyMember(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """家庭成员；deleted_at 非空表示已被移除（不再具有任何权限）。"""

    __tablename__ = "family_members"
    family_id = Column(String, nullable=False, index=True)  # 复合索引建议：(family_id, user_id)
    user_id = Column(String, nullable=False, index=True)
    role = Column(String, default="collaborator", nullable=False)
    # owner | admin | storyteller | collaborator | viewer
    display_name = Column(String, nullable=True)
    invited_by = Column(String, nullable=True)
    joined_at = Column(DateTime, nullable=True)


class FamilyInvitation(UUIDMixin, TimestampMixin, Base):
    """家庭邀请；状态机：pending → accepted | expired | revoked。

    token 唯一且不可预测，服务端校验 expires_at 与 status，前端隐藏按钮不作为鉴权依据。
    """

    __tablename__ = "family_invitations"
    family_id = Column(String, nullable=False, index=True)
    email = Column(String, nullable=False, index=True)
    role = Column(String, default="collaborator")
    token = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, default="pending")  # pending|accepted|expired|revoked
    expires_at = Column(DateTime, nullable=False)
    invited_by = Column(String, nullable=False)
