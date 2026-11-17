"""数字传承（Digital Legacy）：显式授权、可撤销策略，绝不自动交付数据。

安全边界：
- 联系人、策略、事件全部按 user_id 归属；跨用户访问一律 404，杜绝 IDOR。
- 策略创建默认 granted=0 / status=draft；只有本人显式 grant 才激活。
- 任何数据交付都必须经过 trigger-review 人工审核，不提供自动 release 接口。
- share_scope 明确限定可交付的 story / memory ID，空范围表示不交付任何内容。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.deps import get_current_user, get_db
from app.core.security import utcnow
from app.models.legacy import LegacyContact, LegacyEvent, LegacyPolicy

router = APIRouter(prefix="/legacy", tags=["digital-legacy"])

# 明确的分享范围类型：只接受故事与记忆 ID，不接受 "all" / "*" 之类的通配。
ALLOWED_SCOPE_TYPES = {"story", "memory"}
POLICY_STATUSES = {"draft", "active", "disputed", "revoked", "released"}


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    email: str | None = None
    phone: str | None = None
    relationship: str | None = None


class ContactUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    email: str | None = None
    phone: str | None = None
    relationship: str | None = None


class PolicyIn(BaseModel):
    contact_id: str
    trigger: str = "manual"
    release_after_days: int | None = Field(default=None, ge=1, le=3650)
    share_scope: list[str] | None = None


def _validate_policy_input(payload: PolicyIn) -> None:
    """校验策略输入；用 HTTPException 而非 ValueError，兼容全局请求校验错误处理器。"""
    if payload.trigger not in ("manual", "scheduled"):
        raise HTTPException(status_code=422, detail="trigger 必须为 manual / scheduled")
    # share_scope 项格式为 'story:<id>' 或 'memory:<id>'；拒绝 "all"/"*" 等通配符。
    for item in payload.share_scope or []:
        if not isinstance(item, str) or ":" not in item:
            raise HTTPException(status_code=422, detail="share_scope 格式为 'story:<id>' 或 'memory:<id>'")
        kind, rid = item.split(":", 1)
        if kind not in ALLOWED_SCOPE_TYPES or not rid:
            raise HTTPException(status_code=422, detail="share_scope 仅允许 story / memory 类型，且不能为空 ID")


def _owned_contact(db: Session, contact_id: str, user_id: str) -> LegacyContact:
    c = (
        db.query(LegacyContact)
        .filter(LegacyContact.id == contact_id, LegacyContact.user_id == user_id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="传承联系人不存在")
    return c


def _owned_policy(db: Session, policy_id: str, user_id: str) -> LegacyPolicy:
    p = (
        db.query(LegacyPolicy)
        .filter(LegacyPolicy.id == policy_id, LegacyPolicy.user_id == user_id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="策略不存在")
    return p


def _policy_dict(policy: LegacyPolicy) -> dict:
    """策略输出：明确暴露 share_scope 与状态，不泄露任何内部存储路径。"""
    return {
        "id": policy.id,
        "contact_id": policy.contact_id,
        "granted": bool(policy.granted),
        "granted_at": policy.granted_at,
        "revoked_at": policy.revoked_at,
        "trigger": policy.trigger,
        "release_after_days": policy.release_after_days,
        "share_scope": policy.share_scope or [],
        "status": policy.status,
    }


@router.post("/contacts", status_code=201)
def create_contact(payload: ContactIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = LegacyContact(user_id=user.id, **payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    log_action("legacy.contact.create", user_id=user.id, resource_type="legacy_contact", resource_id=c.id)
    return c


@router.get("/contacts")
def list_contacts(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(LegacyContact)
        .filter(LegacyContact.user_id == user.id)
        .order_by(LegacyContact.created_at.desc())
        .all()
    )


@router.put("/contacts/{contact_id}")
def update_contact(
    contact_id: str, payload: ContactUpdateIn, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    c = _owned_contact(db, contact_id, user.id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/contacts/{contact_id}")
def delete_contact(
    contact_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    c = _owned_contact(db, contact_id, user.id)
    # 存在任何策略（含已撤销）时不允许删除联系人，避免策略指向悬空联系人。
    linked = db.query(LegacyPolicy).filter(LegacyPolicy.contact_id == c.id).first()
    if linked:
        raise HTTPException(status_code=400, detail="该联系人已关联访问策略，无法删除")
    db.delete(c)
    db.commit()
    log_action("legacy.contact.delete", user_id=user.id, resource_type="legacy_contact", resource_id=contact_id)
    return {"message": "联系人已删除"}


@router.post("/policies", status_code=201)
def create_policy(payload: PolicyIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _validate_policy_input(payload)
    contact = _owned_contact(db, payload.contact_id, user.id)
    policy = LegacyPolicy(
        user_id=user.id,
        contact_id=contact.id,
        granted=0,  # 必须显式授权，默认为未授权草稿
        trigger=payload.trigger,
        release_after_days=payload.release_after_days,
        share_scope=payload.share_scope or [],  # 不明确指定则不交付任何内容
        status="draft",
    )
    db.add(policy)
    db.flush()
    db.add(
        LegacyEvent(
            policy_id=policy.id,
            event_type="created",
            actor_id=user.id,
            detail=f"share_scope={','.join(policy.share_scope) or '空'}",
        )
    )
    db.commit()
    db.refresh(policy)
    return policy


@router.post("/policies/{policy_id}/grant")
def grant(policy_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    policy = _owned_policy(db, policy_id, user.id)
    if policy.status == "revoked":
        raise HTTPException(status_code=400, detail="已撤销的策略不能再次授权，请新建策略")
    policy.granted = 1
    policy.granted_at = utcnow()
    policy.revoked_at = None
    policy.status = "active"
    db.add(LegacyEvent(policy_id=policy.id, event_type="granted", actor_id=user.id))
    db.commit()
    db.refresh(policy)
    log_action("legacy.grant", user_id=user.id, resource_type="policy", resource_id=policy.id)
    # 向后兼容：旧策略可能没有 share_scope；通过响应字段明确提示，不 silently 扩大范围。
    result = _policy_dict(policy)
    if not policy.share_scope:
        result["warning"] = "该策略未配置分享范围，人工审核时默认不交付任何内容，请补充 share_scope"
    return result


@router.post("/policies/{policy_id}/revoke")
def revoke(policy_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    policy = _owned_policy(db, policy_id, user.id)
    policy.granted = 0
    policy.revoked_at = utcnow()
    policy.status = "revoked"
    db.add(LegacyEvent(policy_id=policy.id, event_type="revoked", actor_id=user.id))
    db.commit()
    db.refresh(policy)
    log_action("legacy.revoke", user_id=user.id, resource_type="policy", resource_id=policy.id)
    return policy


@router.get("/policies")
def list_policies(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(LegacyPolicy)
        .filter(LegacyPolicy.user_id == user.id)
        .order_by(LegacyPolicy.created_at.desc())
        .all()
    )


@router.get("/policies/{policy_id}/events")
def policy_events(policy_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """策略事件时间线：本人才能查看。"""
    _owned_policy(db, policy_id, user.id)
    return (
        db.query(LegacyEvent)
        .filter(LegacyEvent.policy_id == policy_id)
        .order_by(LegacyEvent.created_at.asc())
        .all()
    )


@router.post("/policies/{policy_id}/trigger-review")
def trigger_review(policy_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """触发交付必须进入人工审核（身份核验 + 争议处理），系统绝不自动交付数据。"""
    policy = _owned_policy(db, policy_id, user.id)
    if not policy.granted or policy.status != "active":
        raise HTTPException(status_code=400, detail="策略未激活或未授权")
    db.add(LegacyEvent(policy_id=policy.id, event_type="triggered", actor_id=user.id))
    db.commit()
    log_action("legacy.review.trigger", user_id=user.id, resource_type="policy", resource_id=policy.id)
    return {
        "message": "已进入人工审核流程，需要身份核验与争议处理，不会自动交付数据",
        "policy_id": policy.id,
        "status": policy.status,
    }
