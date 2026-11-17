"""Dynamic AI interviewer: context-aware follow-up, never mechanical, never coercive."""

from __future__ import annotations

import json

from app.ai.factory import get_llm
from app.ai.prompts.registry import interviewer_system

FALLBACK = [
    ({"time"}, "这件事大概发生在什么时候？那时候你多大？"),
    ({"person"}, "当时还有谁在场？他/她在你记忆里是什么样子？"),
    ({"place"}, "那个地方是什么样的？现在还会常想起它吗？"),
    ({"event"}, "能讲讲当时具体发生了什么吗？"),
    ({"emotion"}, "回想起来，你当时心里是什么感受？"),
]

_END_HINTS = ("没有了", "就这些", "想不起来了", "结束", "先这样")


def next_question(history: list[dict], last_answer: str, facts: dict, topic: str | None = None) -> tuple[str, str]:
    if any(h in last_answer for h in _END_HINTS):
        return "", "用户表示结束或想不起来，停止追问"

    context_lines = [f"主题：{topic}" if topic else "主题：人生回忆"]
    for msg in history[-8:]:
        role = "讲述者" if msg.get("role") == "interviewee" else "访谈者"
        context_lines.append(f"{role}：{msg.get('content', '')}")
    context_lines.append(f"最新回答：{last_answer}")
    context_lines.append(f"已识别事实（JSON）：{json.dumps(facts, ensure_ascii=False)}")
    context_lines.append("请结合上下文只输出下一个追问 JSON；如应结束则 follow_up 为空字符串。")
    prompt = "\n".join(context_lines)

    try:
        result = get_llm().generate(interviewer_system(), prompt, json_mode=True, temperature=0.6)
        data = json.loads(result.text)
        question = str(data.get("follow_up", "")).strip()
        reason = str(data.get("reason", ""))
        if question:
            return question, reason
        return "", reason or "信息已足够"
    except Exception:
        pass

    # Deterministic fallback: ask about the least-covered dimension.
    for keys, question in FALLBACK:
        if not any(facts.get(k) for k in keys):
            return question, f"缺少{ '/'.join(keys) }信息"
    return "如果现在再回顾这段经历，你最想对自己说些什么？", "收尾性问题"
