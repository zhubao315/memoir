"""Family Circle: spaces, invitations, role-based resource authorization."""

from __future__ import annotations

import secrets
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.security import utcnow
from app.models.family import Family, FamilyInvitation, FamilyMember

router = APIRouter(prefix="/family", tags=["family-circle"])

ROLES = {"owner", "admin", "storyteller", "collaborator", "viewer"}


def family_role(db: Session, family_id: str, user_id: str) -> str | None:
    m = (
        db.query(FamilyMember)
        .filter(FamilyMember.family_id == family_id, FamilyMember.user_id == user_id, FamilyMember.deleted_at.is_(None))
        .first()
    )
    return m.role if m else None


def require_role(db: Session, family_id: str, user_id: str, allowed: set[str]) -> str:
    role = family_role(db, family_id, user_id)
    if role not in allowed:
        raise HTTPException(status_code=403, detail="没有执行此操作的家庭权限")
    return role


class FamilyIn(BaseModel):
    name: str
    description: str | None = None


class InviteIn(BaseModel):
    email: str
    role: str = "collaborator"


class RoleIn(BaseModel):
    role: str


@router.post("", status_code=201)
def create_family(payload: FamilyIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    family = Family(name=payload.name, description=payload.description, owner_id=user.id)
    db.add(family)
    db.flush()
    db.add(FamilyMember(family_id=family.id, user_id=user.id, role="owner", display_name=user.username, joined_at=utcnow()))
    db.commit()
    db.refresh(family)
    return family


@router.get("")
def list_families(user=Depends(get_current_user), db: Session = Depends(get_db)):
    ids = [m.family_id for m in db.query(FamilyMember).filter(FamilyMember.user_id == user.id, FamilyMember.deleted_at.is_(None)).all()]
    return db.query(Family).filter(Family.id.in_(ids), Family.deleted_at.is_(None)).all()


@router.get("/{family_id}")
def get_family(family_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, family_id, user.id, ROLES)
    return db.query(Family).filter(Family.id == family_id).first()


@router.post("/{family_id}/invite", status_code=201)
def invite(family_id: str, payload: InviteIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, family_id, user.id, {"owner", "admin"})
    if payload.role not in ROLES - {"owner"}:
        raise HTTPException(status_code=400, detail="无效角色")
    token = secrets.token_urlsafe(24)
    inv = FamilyInvitation(
        family_id=family_id,
        email=payload.email,
        role=payload.role,
        token=token,
        status="pending",
        expires_at=utcnow() + timedelta(days=7),
        invited_by=user.id,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return {"token": inv.token, "invite_url": f"/family/invite/{inv.token}", "expires_at": inv.expires_at}


@router.post("/invite/{token}/accept")
def accept_invite(token: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    inv = db.query(FamilyInvitation).filter(FamilyInvitation.token == token).first()
    now_naive = utcnow().replace(tzinfo=None)  # SQLite DATETIME columns are naive
    if not inv or inv.status != "pending" or inv.expires_at.replace(tzinfo=None) < now_naive:
        raise HTTPException(status_code=400, detail="邀请无效或已过期")
    existing = (
        db.query(FamilyMember)
        .filter(FamilyMember.family_id == inv.family_id, FamilyMember.user_id == user.id)
        .first()
    )
    if not existing:
        db.add(
            FamilyMember(
                family_id=inv.family_id,
                user_id=user.id,
                role=inv.role,
                display_name=user.username,
                invited_by=inv.invited_by,
                joined_at=utcnow(),
            )
        )
    inv.status = "accepted"
    db.commit()
    return {"message": "已加入家庭", "family_id": inv.family_id}


@router.get("/{family_id}/members")
def members(family_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, family_id, user.id, ROLES)
    return db.query(FamilyMember).filter(FamilyMember.family_id == family_id, FamilyMember.deleted_at.is_(None)).all()


@router.put("/{family_id}/members/{member_id}")
def change_role(family_id: str, member_id: str, payload: RoleIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, family_id, user.id, {"owner", "admin"})
    if payload.role not in ROLES:
        raise HTTPException(status_code=400, detail="无效角色")
    member = db.query(FamilyMember).filter(FamilyMember.id == member_id, FamilyMember.family_id == family_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    if member.role == "owner":
        raise HTTPException(status_code=403, detail="不能修改所有者角色")
    member.role = payload.role
    db.commit()
    return member


@router.delete("/{family_id}/members/{member_id}")
def remove_member(family_id: str, member_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, family_id, user.id, {"owner", "admin"})
    member = db.query(FamilyMember).filter(FamilyMember.id == member_id, FamilyMember.family_id == family_id).first()
    if not member or member.role == "owner":
        raise HTTPException(status_code=403, detail="无法移除该成员")
    member.deleted_at = utcnow()
    db.commit()
    return {"message": "已移除成员"}
