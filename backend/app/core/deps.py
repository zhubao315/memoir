"""FastAPI dependency injection: DB session, current user, token type & denylist checks."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token, require_token_type
from app.db.session import SessionLocal
from app.models.identity import TokenDenylist
from app.models.legacy_tables import User

bearer = HTTPBearer(auto_error=False)

credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="无法验证凭证",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _is_revoked(db: Session, token: str, jti: str) -> bool:
    from app.core.security import hash_token

    return (
        db.query(TokenDenylist)
        .filter((TokenDenylist.token_hash == hash_token(token)) | (TokenDenylist.jti == jti))
        .first()
        is not None
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials or not credentials.credentials:
        raise credentials_error
    token = credentials.credentials
    try:
        payload = decode_token(token)
        require_token_type(payload, "access")
    except Exception:  # JWTError / TokenError / decode failures all => 401
        raise credentials_error
    if _is_revoked(db, token, payload.get("jti", "")):
        raise credentials_error
    # P1: prefer stable UUID in sub; fallback to username for legacy tokens.
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if user is None:
        user = db.query(User).filter(User.username == payload.get("sub")).first()
    if user is None:
        raise credentials_error
    return user


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """For public QR story pages: validate token if present, else None."""
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    token = header.split(" ", 1)[1]
    try:
        payload = decode_token(token)
        require_token_type(payload, "access")
        if _is_revoked(db, token, payload.get("jti", "")):
            return None
        return db.query(User).filter(User.id == payload.get("sub")).first()
    except Exception:
        return None
