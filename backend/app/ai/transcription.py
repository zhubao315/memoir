"""ASR orchestration wrapper."""

from __future__ import annotations

from app.ai.factory import get_asr


def transcribe(data: bytes, filename: str, mime_type: str, *, language: str | None = None) -> tuple[str, dict]:
    return get_asr().transcribe(data, filename, mime_type, language=language)
