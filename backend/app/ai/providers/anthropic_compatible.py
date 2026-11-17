"""Anthropic-compatible messages adapter (chat only; embeddings via fallback provider)."""

from __future__ import annotations

import time

import httpx

from app.ai.providers.base import GenerationResult, LLMProvider
from app.core.config import settings


class AnthropicCompatibleLLM(LLMProvider):
    name = "anthropic_compatible"

    def __init__(self):
        if not settings.AI_BASE_URL or not settings.AI_API_KEY:
            raise RuntimeError("AI_BASE_URL and AI_API_KEY must be configured")
        self.client = httpx.Client(
            base_url=settings.AI_BASE_URL.rstrip("/"),
            headers={
                "x-api-key": settings.AI_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            timeout=60.0,
        )

    def generate(self, system, user, *, model=None, temperature=0.7, max_tokens=1500, json_mode=False) -> GenerationResult:
        start = time.time()
        payload = {
            "model": model or settings.AI_MODEL_STORY,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        r = self.client.post("/v1/messages", json=payload)
        r.raise_for_status()
        data = r.json()
        text = "".join(block.get("text", "") for block in data.get("content", []))
        return GenerationResult(
            text=text,
            provider=self.name,
            model=payload["model"],
            prompt_version="see-system-prompt",
            latency_ms=int((time.time() - start) * 1000),
            raw=data,
        )

    def embed(self, texts, model=None):
        raise NotImplementedError(
            "Anthropic has no embeddings endpoint; configure EMBEDDING_PROVIDER=openai_compatible or use local."
        )
