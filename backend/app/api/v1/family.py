"""家庭空间（Family Circle）：多家庭、成员角色与服务端资源级鉴权。

设计要点：
- 所有家庭资源（家庭详情、成员、邀请）都先做「成员身份 + 角色」校验，绝不依赖前端隐藏按钮。
- 角色分级：owner > admin > storyteller > collaborator > viewer。
- 邀请 token：有有效期、只能接受一次、可被 owner/admin 撤销；多家庭互不串号。
- 审计：角色变更、成员移除、邀请/撤销等关键操作写入审计日志。
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.deps import get_current_user, get_db
from app.core.security import utcnow
from app.models.family import Family, FamilyInvitation, FamilyMember

router = APIRouter(prefix="/family", tags=["family-circle"])

ROLES = {"owner", "admin", "storyteller", "collaborator", "viewer"}
# 角色等级：仅用于「谁可以管理谁」的判断，不等同于能力矩阵（见 DATA_MODEL_FAMILY_LEGACY.md）。
ROLE_LEVEL = {"viewer": 1, "collaborator": 2, "storyteller": 3, "admin": 4, "owner": 5}
MANAGER_ROLES = {"owner", "admin"}


def family_role(db: Session, family_id: str, user_id: str) -> str | None:
    """返回用户在指定家庭中的有效角色；非成员（含已移除成员）返回 None。"""
    m = (
        db.query(FamilyMember)
        .filter(
            FamilyMember.family_id == family_id,
            FamilyMember.user_id == user_id,
            FamilyMember.deleted_at.is_(None),
        )
        .first()
    )
    return m.role if m else None


def require_role(db: Session, family_id: str, user_id: str, allowed: set[str]) -> str:
    """资源级鉴权：用户必须是该家庭成员且角色在 allowed 中。"""
    role = family_role(db, family_id, user_id)
    if role not in allowed:
        raise HTTPException(status_code=403, detail="没有执行此操作的家庭权限")
    return role


def _require_live_family(db: Session, family_id: str) -> Family:
    family = (
        db.query(Family)
        .filter(Family.id == family_id, Family.deleted_at.is_(None))
        .first()
    )
    if not family:
        raise HTTPException(status_code=404, detail="家庭空间不存在")
    return family


def _now_naive():
    """SQLite 的 DATETIME 列不带时区，比较前统一去掉 tzinfo。"""
    return utcnow().replace(tzinfo=None)


def _expiry(value) -> bool:
    """邀请是否已过期。"""
    return value is not None and value.replace(tzinfo=None) < _now_naive()


class FamilyIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class InviteIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role: str = "collaborator"
    # 可配置邀请有效期（天），默认 7 天；限制在 1~30 天，防止永久有效的 token。
    expires_in_days: int = Field(default=7, ge=1, le=30)


class RoleIn(BaseModel):
    role: str


@router.post("", status_code=201)
def create_family(payload: FamilyIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    family = Family(name=payload.name, description=payload.description, owner_id=user.id)
    db.add(family)
    db.flush()
    db.add(
        FamilyMember(
            family_id=family.id,
            user_id=user.id,
            role="owner",
            display_name=user.username,
            joined_at=utcnow(),
        )
    )
    db.commit()
    db.refresh(family)
    log_action("family.create", user_id=user.id, resource_type="family", resource_id=family.id)
    return family


@router.get("")
def list_families(user=Depends(get_current_user), db: Session = Depends(get_db)):
    # 多家庭：只返回当前用户仍是有效成员的空间。
    ids = [
        m.family_id
        for m in db.query(FamilyMember)
        .filter(FamilyMember.user_id == user.id, FamilyMember.deleted_at.is_(None))
        .all()
    ]
    return (
        db.query(Family)
        .filter(Family.id.in_(ids), Family.deleted_at.is_(None))
        .order_by(Family.created_at.desc())
        .all()
    )


@router.get("/{family_id}")
def get_family(family_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, family_id, user.id, ROLES)
    return _require_live_family(db, family_id)


@router.post("/{family_id}/invite", status_code=201)
def invite(family_id: str, payload: InviteIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, family_id, user.id, MANAGER_ROLES)
    _require_live_family(db, family_id)
    if payload.role not in ROLES - {"owner"}:
        raise HTTPException(status_code=400, detail="无效角色（不能通过邀请授予所有者）")
    inv = FamilyInvitation(
        family_id=family_id,
        email=payload.email,
        role=payload.role,
        token=secrets.token_urlsafe(24),
        status="pending",
        expires_at=utcnow() + timedelta(days=payload.expires_in_days),
        invited_by=user.id,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    log_action(
        "family.invite",
        user_id=user.id,
        resource_type="family",
        resource_id=family_id,
        detail=f"role={payload.role}, expires_in_days={payload.expires_in_days}",
    )
    return {
        "id": inv.id,
        "token": inv.token,
        "invite_url": f"/family/invite/{inv.token}",
        "expires_at": inv.expires_at,
        "status": inv.status,
        "role": inv.role,
    }


@router.get("/{family_id}/invitations")
def list_invitations(family_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """列出家庭邀请，供前端展示有效期/状态并撤销（仅 owner/admin）。"""
    require_role(db, family_id, user.id, MANAGER_ROLES)
    return (
        db.query(FamilyInvitation)
        .filter(FamilyInvitation.family_id == family_id)
        .order_by(FamilyInvitation.created_at.desc())
        .all()
    )


@router.post("/{family_id}/invitations/{invitation_id}/revoke")
def revoke_invitation(
    family_id: str, invitation_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    require_role(db, family_id, user.id, MANAGER_ROLES)
    inv = (
        db.query(FamilyInvitation)
        .filter(FamilyInvitation.id == invitation_id, FamilyInvitation.family_id == family_id)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="邀请不存在")
    if inv.status == "pending":
        inv.status = "revoked"
        db.commit()
        log_action(
            "family.invitation.revoke",
            user_id=user.id,
            resource_type="family_invitation",
            resource_id=inv.id,
        )
    return {"message": "邀请已撤销", "status": inv.status}


@router.post("/invite/{token}/accept")
def accept_invite(token: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    inv = db.query(FamilyInvitation).filter(FamilyInvitation.token == token).first()
    if not inv or inv.status != "pending":
        raise HTTPException(status_code=400, detail="邀请无效、已使用或已撤销")
    if _expiry(inv.expires_at):
        inv.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="邀请已过期")
    # 家庭被删除后邀请不可再接受。
    _require_live_family(db, inv.family_id)

    existing = (
        db.query(FamilyMember)
        .filter(FamilyMember.family_id == inv.family_id, FamilyMember.user_id == user.id)
        .first()
    )
    if existing and existing.deleted_at is not None:
        # 曾被移除的成员重新受邀：恢复成员身份，但角色以新邀请为准。
        existing.deleted_at = None
        existing.role = inv.role
        existing.joined_at = utcnow()
    elif not existing:
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
    # 已是有效成员时不降级其现有角色（多家庭场景下可能已拥有更高角色）。
    inv.status = "accepted"
    db.commit()
    log_action(
        "family.invitation.accept",
        user_id=user.id,
        resource_type="family",
        resource_id=inv.family_id,
    )
    return {"message": "已加入家庭", "family_id": inv.family_id, "role": family_role(db, inv.family_id, user.id)}


@router.get("/{family_id}/members")
def members(family_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, family_id, user.id, ROLES)
    return (
        db.query(FamilyMember)
        .filter(FamilyMember.family_id == family_id, FamilyMember.deleted_at.is_(None))
        .order_by(FamilyMember.created_at.asc())
        .all()
    )


@router.put("/{family_id}/members/{member_id}")
def change_role(
    family_id: str, member_id: str, payload: RoleIn, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    caller_role = require_role(db, family_id, user.id, MANAGER_ROLES)
    if payload.role not in ROLES:
        raise HTTPException(status_code=400, detail="无效角色")
    if payload.role == "owner":
        raise HTTPException(status_code=403, detail="不能通过角色变更授予所有者")
    member = (
        db.query(FamilyMember)
        .filter(
            FamilyMember.id == member_id,
            FamilyMember.family_id == family_id,
            FamilyMember.deleted_at.is_(None),
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    if member.user_id == user.id:
        raise HTTPException(status_code=403, detail="不能修改自己的角色")
    if member.role == "owner":
        raise HTTPException(status_code=403, detail="不能修改所有者角色")
    # 管理员只能管理比自己低级的成员；管理员之间的任免由所有者负责。
    if caller_role != "owner" and ROLE_LEVEL.get(member.role, 0) >= ROLE_LEVEL["admin"]:
        raise HTTPException(status_code=403, detail="只有所有者可以管理管理员")
    if caller_role != "owner" and payload.role == "admin":
        raise HTTPException(status_code=403, detail="只有所有者可以授予管理员角色")
    member.role = payload.role
    db.commit()
    log_action(
        "family.member.role",
        user_id=user.id,
        resource_type="family_member",
        resource_id=member.id,
        detail=f"{member.role} 由 {caller_role} 变更",
    )
    return member


@router.delete("/{family_id}/members/{member_id}")
def remove_member(family_id: str, member_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    caller_role = require_role(db, family_id, user.id, MANAGER_ROLES)
    member = (
        db.query(FamilyMember)
        .filter(
            FamilyMember.id == member_id,
            FamilyMember.family_id == family_id,
            FamilyMember.deleted_at.is_(None),
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    if member.role == "owner" or member.user_id == user.id:
        raise HTTPException(status_code=403, detail="无法移除该成员")
    if caller_role != "owner" and ROLE_LEVEL.get(member.role, 0) >= ROLE_LEVEL["admin"]:
        raise HTTPException(status_code=403, detail="只有所有者可以移除管理员")
    member.deleted_at = utcnow()
    db.commit()
    log_action(
        "family.member.remove",
        user_id=user.id,
        resource_type="family_member",
        resource_id=member.id,
    )
    return {"message": "已移除成员"}
