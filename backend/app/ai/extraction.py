"""Fact extraction (time/person/place/event/emotion) with fact protection."""

from __future__ import annotations

import json
import re

from app.ai.factory import get_llm
from app.ai.prompts.registry import PROMPT_VERSION, extraction_system

_KEYWORDS = {
    "time": ["小时候", "童年", "少年", "青年", "大学", "中学", "小学", "那年", "去年", "今年", "春天", "夏天", "秋天", "冬天"],
    "person": ["父亲", "母亲", "爸爸", "妈妈", "祖父", "祖母", "爷爷", "奶奶", "朋友", "同学", "妻子", "丈夫", "儿子", "女儿", "兄弟", "姐妹"],
    "place": ["北京", "上海", "什刹海", "故宫", "学校", "家", "公园", "医院", "工厂"],
    "emotion": ["快乐", "开心", "怀念", "难过", "难忘", "幸福", "害怕", "骄傲"],
}


def _regex_facts(text: str) -> dict:
    return {key: [k for k in words if k in text] for key, words in _KEYWORDS.items()} | {"event": []}


def extract_facts(text: str) -> dict:
    """Best-effort extraction; always bounded to words actually present in text."""
    regex_facts = _regex_facts(text)
    try:
        result = get_llm().generate(extraction_system(), text, json_mode=True, temperature=0.0)
        data = json.loads(result.text)
        facts = data.get("facts", {})
        # Fact guard: drop any model-returned item not present in the source text.
        cleaned = {}
        for key, values in facts.items():
            if not isinstance(values, list):
                continue
            cleaned[key] = [v for v in values if isinstance(v, str) and v.strip() and v.strip() in text][:10]
        for key, values in regex_facts.items():
            cleaned.setdefault(key, [])
            for v in values:
                if v not in cleaned[key]:
                    cleaned[key].append(v)
        return cleaned
    except Exception:
        return regex_facts


DATE_PATTERN = re.compile(r"(19|20)\d{2}年|\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2}")
