"""v1 auth endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.ratelimit import check_rate_limit, client_key
from app.schemas.auth import ChangePasswordIn, LoginIn, MessageOut, RefreshIn, RegisterIn, TokenPair, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut)
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(client_key(request, "register"))
    return auth_service.register(db, payload.username, payload.email, payload.password)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(client_key(request, "login", payload.username))
    return auth_service.login(db, payload.username, payload.password, request=request)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)):
    return auth_service.refresh(db, payload.refresh_token)


@router.post("/logout", response_model=MessageOut)
def logout(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    token = request.headers.get("Authorization", "").split(" ", 1)[1]
    return auth_service.logout(db, user.id, token)


@router.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return user


@router.post("/change-password", response_model=MessageOut)
def change_password(payload: ChangePasswordIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.core.security import get_password_hash, verify_password
    if not verify_password(payload.old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码不正确")
    user.hashed_password = get_password_hash(payload.new_password)
    from app.services.auth import _revoke_all
    _revoke_all(db, user.id)  # 改密后撤销全部会话，需重新登录
    db.commit()
    from app.core.audit import log_action
    log_action("password.changed", user_id=user.id)
    return {"message": "密码已修改，请重新登录"}


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.models.identity import RefreshToken
    rows = db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None), RefreshToken.used_at.is_(None)
    ).all()
    return [{"id": r.id, "created_at": r.created_at, "expires_at": r.expires_at} for r in rows]
