"""Password hashing and JWT issue/verify (S-01, S-06, S-07)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_password_hash(password: str) -> str:
    raw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _make_token(sub: str, token_type: str, expires: timedelta, extra: dict[str, Any] | None = None) -> tuple[str, str, datetime]:
    jti = str(uuid.uuid4())
    now = utcnow()
    expire = now + expires
    payload: dict[str, Any] = {
        "sub": sub,
        "type": token_type,
        "iat": now,
        "exp": expire,
        "jti": jti,
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expire


def create_access_token(sub: str, extra: dict[str, Any] | None = None) -> tuple[str, str, datetime]:
    return _make_token(sub, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), extra)


def create_refresh_token(sub: str) -> tuple[str, str, datetime]:
    return _make_token(sub, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def decode_token(token: str) -> dict[str, Any]:
    """Decode & validate signature/exp. Caller must check type and denylist."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def hash_token(token: str) -> str:
    """Hash a token for safe storage in the denylist (never store raw tokens)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TokenError(Exception):
    pass


def require_token_type(payload: dict[str, Any], expected: str) -> None:
    if payload.get("type") != expected:
        raise TokenError(f"expected {expected} token")
