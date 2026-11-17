"""Digital Legacy: explicit consent, revocable policies, no automatic handover."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.deps import get_current_user, get_db
from app.core.security import utcnow
from app.models.legacy import LegacyContact, LegacyEvent, LegacyPolicy

router = APIRouter(prefix="/legacy", tags=["digital-legacy"])


class ContactIn(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    relationship: str | None = None


class PolicyIn(BaseModel):
    contact_id: str
    trigger: str = "manual"
    release_after_days: int | None = None
    share_scope: list[str] | None = None


@router.post("/contacts", status_code=201)
def create_contact(payload: ContactIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = LegacyContact(user_id=user.id, **payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.get("/contacts")
def list_contacts(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(LegacyContact).filter(LegacyContact.user_id == user.id).all()


@router.post("/policies", status_code=201)
def create_policy(payload: PolicyIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    contact = db.query(LegacyContact).filter(LegacyContact.id == payload.contact_id, LegacyContact.user_id == user.id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="传承联系人不存在")
    policy = LegacyPolicy(
        user_id=user.id,
        contact_id=contact.id,
        granted=0,
        trigger=payload.trigger,
        release_after_days=payload.release_after_days,
        share_scope=payload.share_scope or [],
        status="draft",
    )
    db.add(policy)
    db.flush()
    db.add(LegacyEvent(policy_id=policy.id, event_type="created", actor_id=user.id))
    db.commit()
    db.refresh(policy)
    return policy


@router.post("/policies/{policy_id}/grant")
def grant(policy_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    policy = db.query(LegacyPolicy).filter(LegacyPolicy.id == policy_id, LegacyPolicy.user_id == user.id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")
    policy.granted = 1
    policy.granted_at = utcnow()
    policy.revoked_at = None
    policy.status = "active"
    db.add(LegacyEvent(policy_id=policy.id, event_type="granted", actor_id=user.id))
    db.commit()
    log_action("legacy.grant", user_id=user.id, resource_type="policy", resource_id=policy.id)
    return policy


@router.post("/policies/{policy_id}/revoke")
def revoke(policy_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    policy = db.query(LegacyPolicy).filter(LegacyPolicy.id == policy_id, LegacyPolicy.user_id == user.id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")
    policy.granted = 0
    policy.revoked_at = utcnow()
    policy.status = "revoked"
    db.add(LegacyEvent(policy_id=policy.id, event_type="revoked", actor_id=user.id))
    db.commit()
    log_action("legacy.revoke", user_id=user.id, resource_type="policy", resource_id=policy.id)
    return policy


@router.get("/policies")
def list_policies(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(LegacyPolicy).filter(LegacyPolicy.user_id == user.id).all()


@router.post("/policies/{policy_id}/trigger-review")
def trigger_review(policy_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Legacy release always requires explicit, verified, manual review — never automatic."""
    policy = db.query(LegacyPolicy).filter(LegacyPolicy.id == policy_id, LegacyPolicy.user_id == user.id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")
    if not policy.granted or policy.status != "active":
        raise HTTPException(status_code=400, detail="策略未激活或未授权")
    db.add(LegacyEvent(policy_id=policy.id, event_type="triggered", actor_id=user.id))
    db.commit()
    return {"message": "已进入人工审核流程，需要身份核验与争议处理，不会自动交付数据"}
