"""数字传承：联系人、显式授权策略与事件（绝不自动交付数据）。

状态机（详见 docs/architecture/DATA_MODEL_FAMILY_LEGACY.md）：
- 策略 status：draft → active（grant）→ revoked / disputed / released。
- granted=0 时任何交付请求都拒绝；trigger-review 只进入人工审核，不自动 release。
- share_scope 明确限定可交付的 story:<id> / memory:<id>，空范围表示不交付任何内容。
"""

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDMixin


class LegacyContact(UUIDMixin, TimestampMixin, Base):
    """传承联系人；user_id 为所有者，只有本人可管理。"""

    __tablename__ = "legacy_contacts"
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    relationship = Column(String, nullable=True)
    identity_verified = Column(Integer, default=0)  # 人工核验结果，非自动
    verification_method = Column(String, nullable=True)


class LegacyPolicy(UUIDMixin, TimestampMixin, Base):
    """访问策略；必须显式 grant，且任何交付都需人工审核。"""

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
    """策略事件；用于时间线审计（created|granted|revoked|triggered|verified|disputed|released）。"""

    __tablename__ = "legacy_events"
    policy_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)  # granted|revoked|triggered|verified|disputed|released
    actor_id = Column(String, nullable=True)
    detail = Column(Text, nullable=True)
