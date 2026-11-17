"""Simple in-memory sliding-window rate limiter (S-08). Swap for Redis in production."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import settings

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str, limit: int | None = None, window: int | None = None) -> None:
    limit = limit or settings.LOGIN_RATE_LIMIT
    window = window or settings.LOGIN_RATE_WINDOW_SECONDS
    now = time.time()
    with _lock:
        bucket = _hits[key]
        while bucket and bucket[0] < now - window:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="请求过于频繁，请稍后再试")
        bucket.append(now)


def client_key(request: Request, scope: str, identity: str = "") -> str:
    ip = request.client.host if request.client else "unknown"
    return f"{scope}:{ip}:{identity}"
