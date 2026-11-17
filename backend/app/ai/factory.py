"""Provider factories — no model/key/URL is ever hardcoded in business code."""

from functools import lru_cache

from app.ai.providers.base import ASRProvider, LLMProvider
from app.core.config import settings


@lru_cache
def get_llm() -> LLMProvider:
    kind = settings.AI_PROVIDER.lower()
    if kind == "openai_compatible":
        from app.ai.providers.openai_compatible import OpenAICompatibleLLM

        return OpenAICompatibleLLM()
    if kind == "anthropic_compatible":
        from app.ai.providers.anthropic_compatible import AnthropicCompatibleLLM

        return AnthropicCompatibleLLM()
    if kind == "local":
        # Local model support: use an OpenAI-compatible endpoint (e.g. llama.cpp / vLLM).
        from app.ai.providers.openai_compatible import OpenAICompatibleLLM

        return OpenAICompatibleLLM()
    from app.ai.providers.mock import MockLLM

    return MockLLM()


@lru_cache
def get_asr() -> ASRProvider:
    kind = settings.ASR_PROVIDER.lower()
    if kind == "openai_compatible":
        from app.ai.providers.openai_compatible import OpenAICompatibleASR

        return OpenAICompatibleASR()
    from app.ai.providers.mock import MockASR

    return MockASR()
