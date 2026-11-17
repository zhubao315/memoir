"""OpenAI-compatible chat + embeddings + whisper adapters (real network calls)."""

from __future__ import annotations

import time

import httpx

from app.ai.providers.base import ASRProvider, GenerationResult, LLMProvider
from app.core.config import settings


class OpenAICompatibleLLM(LLMProvider):
    name = "openai_compatible"

    def __init__(self):
        if not settings.AI_BASE_URL or not settings.AI_API_KEY:
            raise RuntimeError("AI_BASE_URL and AI_API_KEY must be configured for openai_compatible provider")
        self.base = settings.AI_BASE_URL.rstrip("/")
        self.client = httpx.Client(
            base_url=self.base,
            headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
            timeout=60.0,
        )

    def generate(self, system, user, *, model=None, temperature=0.7, max_tokens=1500, json_mode=False) -> GenerationResult:
        start = time.time()
        payload = {
            "model": model or settings.AI_MODEL_STORY,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        r = self.client.post("/chat/completions", json=payload)
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        return GenerationResult(
            text=text,
            provider=self.name,
            model=payload["model"],
            prompt_version="see-system-prompt",
            latency_ms=int((time.time() - start) * 1000),
            raw=data,
        )

    def embed(self, texts, model=None):
        r = self.client.post(
            "/embeddings",
            json={"model": model or settings.AI_MODEL_EMBEDDING, "input": texts},
        )
        r.raise_for_status()
        return [item["embedding"] for item in sorted(r.json()["data"], key=lambda x: x.get("index", 0))]


class OpenAICompatibleASR(ASRProvider):
    name = "openai_compatible"

    def __init__(self):
        if not settings.ASR_BASE_URL:
            raise RuntimeError("ASR_BASE_URL must be configured")
        # 服务可无需 API Key（如本地 qwen3-asr）。仅在配置了 Key 时才发送鉴权头。
        headers = {"Authorization": f"Bearer {settings.ASR_API_KEY}"} if settings.ASR_API_KEY else {}
        self.client = httpx.Client(
            base_url=settings.ASR_BASE_URL.rstrip("/"),
            headers=headers,
            timeout=180.0,
        )

    def transcribe(self, data, filename, mime_type, *, language=None):
        files = {"file": (filename, data, mime_type)}
        payload = {"model": settings.ASR_MODEL}
        if language:
            payload["language"] = language
        r = self.client.post("/audio/transcriptions", data=payload, files=files)
        r.raise_for_status()
        result = r.json()
        return result.get("text", ""), result
