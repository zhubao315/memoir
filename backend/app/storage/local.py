"""Local filesystem storage adapter with path-traversal protection and signed URLs."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import quote

from app.core.config import settings
from app.storage.base import StorageBackend, StoredObject


class LocalStorage(StorageBackend):
    def __init__(self, root: Path | None = None, secret: str | None = None):
        self.root = (root or settings.upload_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._secret = (secret or settings.SECRET_KEY).encode("utf-8")

    def _safe_path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if self.root not in candidate.parents and candidate != self.root:
            raise ValueError("path traversal detected")
        return candidate

    def save(self, key: str, data: bytes, mime_type: str) -> StoredObject:
        path = self._safe_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(key=key, size=len(data), sha256=hashlib.sha256(data).hexdigest(), mime_type=mime_type)

    def read(self, key: str) -> bytes:
        return self._safe_path(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._safe_path(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._safe_path(key).exists()

    def _sign(self, payload: dict) -> str:
        body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
        sig = hmac.new(self._secret, body.encode(), hashlib.sha256).hexdigest()
        return f"{body}.{sig}"

    def signed_url(self, key: str, expires_in: int, filename: str | None = None) -> str:
        token = self._sign({"key": key, "f": filename, "exp": int(time.time()) + expires_in})
        return f"/api/v1/media/file?token={quote(token)}"

    def resolve_signed_token(self, token: str, max_age: int | None = None) -> dict:
        try:
            body, sig = token.rsplit(".", 1)
        except ValueError as exc:
            raise ValueError("invalid media token") from exc
        expected = hmac.new(self._secret, body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("invalid media token signature")
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if payload.get("exp", 0) < int(time.time()):
            raise ValueError("expired media token")
        return payload
