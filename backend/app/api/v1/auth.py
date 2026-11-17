"""v1 auth endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.ratelimit import check_rate_limit, client_key
from app.schemas.auth import LoginIn, MessageOut, RefreshIn, RegisterIn, TokenPair, UserOut
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
