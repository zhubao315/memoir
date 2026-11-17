"""Authentication service: register, login, refresh rotation, logout/revocation."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    hash_token,
    utcnow,
    verify_password,
)
from app.models.identity import RefreshToken, TokenDenylist
from app.models.legacy_tables import User


def register(db: Session, username: str, email: str, password: str) -> User:
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="邮箱已存在")
    user = User(username=username, email=email, hashed_password=get_password_hash(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    log_action("register", user_id=user.id)
    return user


def issue_tokens(db: Session, user: User, *, request=None) -> dict:
    access, _, _ = create_access_token(sub=user.id)
    refresh, jti, expires = create_refresh_token(sub=user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh),
            jti=jti,
            expires_at=expires,
        )
    )
    db.commit()
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user,
    }


def login(db: Session, username: str, password: str, *, request=None) -> dict:
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    log_action("login", user_id=user.id, request=request)
    return issue_tokens(db, user, request=request)


def refresh(db: Session, refresh_token: str) -> dict:
    from app.core.security import decode_token

    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=401, detail="refresh token 无效")

    record = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_token(refresh_token)).first()
    if not record or record.revoked_at or record.used_at:
        raise HTTPException(status_code=401, detail="refresh token 已失效")
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    # Rotation: mark old token used, revoke it, issue a new pair.
    now = utcnow()
    record.used_at = now
    record.revoked_at = now
    db.commit()
    tokens = issue_tokens(db, user)
    record.replaced_by = tokens["refresh_token"][:16] + "..."
    db.commit()
    return tokens


def _revoke_all(db: Session, user_id: str) -> None:
    now = utcnow()
    for rt in db.query(RefreshToken).filter(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)).all():
        rt.revoked_at = now
    db.commit()


def logout(db: Session, user_id: str, access_token: str) -> dict:
    from app.core.security import decode_token

    try:
        from datetime import datetime, timezone

        payload = decode_token(access_token)
        exp = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc).replace(tzinfo=None)
        db.add(
            TokenDenylist(
                token_hash=hash_token(access_token),
                jti=payload.get("jti", ""),
                revoked_at=utcnow(),
                expires_at=exp,
            )
        )
        db.commit()
    except Exception:
        pass
    _revoke_all(db, user_id)
    log_action("logout", user_id=user_id)
    return {"message": "已退出登录"}
