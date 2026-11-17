"""Story generation with fact protection & traceable output (原则 A/C)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ai.extraction import DATE_PATTERN, extract_facts
from app.ai.factory import get_llm
from app.ai.prompts.registry import PROMPT_VERSION, story_system


@dataclass
class StoryDraft:
    content: str
    mode: str
    provider: str
    model: str
    prompt_version: str
    needs_confirmation: list[str] = field(default_factory=list)


def _fact_guard(content: str, source: str) -> list[str]:
    """Flag any suspicious date/name that appears in output but not in the source."""
    suspicious: list[str] = []
    for m in DATE_PATTERN.finditer(content):
        token = m.group(0)
        if token not in source:
            suspicious.append(f"日期「{token}」未在原始讲述中出现")
    return list(dict.fromkeys(suspicious))


def generate_story(
    raw_text: str,
    mode: str = "first_person",
    *,
    title: str | None = None,
    facts: dict | None = None,
    length: str = "medium",
    tone: str = "warm",
) -> StoryDraft:
    facts = facts or extract_facts(raw_text)
    source_lines = [raw_text.strip()]
    if title:
        source_lines.insert(0, f"标题：{title}")
    known = "；".join(f"{k}: {'、'.join(v)}" for k, v in facts.items() if v)
    user = "\n".join(
        [
            "讲述内容：",
            *source_lines,
            "",
            f"已知事实：{known or '无'}",
        ]
    )
    result = get_llm().generate(story_system(mode, length, tone), user, temperature=0.7, max_tokens=1800)
    needs = _fact_guard(result.text, raw_text)
    return StoryDraft(
        content=result.text,
        mode=mode,
        provider=result.provider,
        model=result.model,
        prompt_version=result.prompt_version or PROMPT_VERSION,
        needs_confirmation=needs,
    )
