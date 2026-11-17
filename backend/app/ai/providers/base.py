"""Provider-agnostic LLM / ASR interfaces. Business code imports only these."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass
class GenerationResult:
    text: str
    provider: str
    model: str
    prompt_version: str
    latency_ms: int = 0
    raw: dict = field(default_factory=dict)


class LLMProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def generate(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1500,
        json_mode: bool = False,
    ) -> GenerationResult: ...

    @abc.abstractmethod
    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]: ...


class ASRProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def transcribe(self, data: bytes, filename: str, mime_type: str, *, language: str | None = None) -> tuple[str, dict]:
        """Return (transcript_text, raw_response)."""
        ...
