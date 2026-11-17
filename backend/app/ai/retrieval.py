"""Private RAG over user-scoped embeddings, with mandatory citations (P2 foundation)."""

from __future__ import annotations

import math

from sqlalchemy.orm import Session

from app.ai.factory import get_llm
from app.ai.prompts.registry import rag_system
from app.models.ai import Embedding
from app.models.memory import Memory
from app.models.story import Story, StoryVersion


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(v * v for v in a[:n]))
    nb = math.sqrt(sum(v * v for v in b[:n]))
    return dot / (na * nb) if na and nb else 0.0


def _source_text(db: Session, e: Embedding) -> str:
    if e.resource_type == "memory":
        obj = db.query(Memory).filter(Memory.id == e.resource_id, Memory.user_id == e.user_id).first()
        return (obj.title or "") + "\n" + (obj.raw_content or "") if obj else ""
    if e.resource_type == "story":
        obj = db.query(Story).filter(Story.id == e.resource_id, Story.user_id == e.user_id).first()
        if not obj:
            return ""
        version = (
            db.query(StoryVersion)
            .filter(StoryVersion.id == obj.current_version_id)
            .first()
            if obj.current_version_id
            else None
        )
        return (obj.title or "") + "\n" + (version.content if version else obj.summary or "")
    return ""


def retrieve(db: Session, user_id: str, query: str, top_k: int = 5, family_id: str | None = None) -> list[dict]:
    query_vec = get_llm().embed([query])[0]
    q = db.query(Embedding).filter(Embedding.user_id == user_id)
    if family_id:
        q = q.filter((Embedding.family_id == family_id) | (Embedding.family_id.is_(None)))
    scored = [(_cosine(query_vec, r.vector or []), r) for r in q.all()]
    scored = [item for item in scored if item[0] > 0.05]
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for score, r in scored[:top_k]:
        text = _source_text(db, r)
        if not text:
            continue
        # Honesty guard for the offline Mock: weak hash embeddings can produce
        # spurious similarity. Require at least one shared meaningful term so we
        # never fabricate an answer to an unrelated question. Real embedding
        # providers skip this lexical check via their stronger vectors.
        from app.core.config import settings

        if settings.AI_PROVIDER.lower() == "mock":
            terms = {query[i:i+2] for i in range(len(query) - 1) if not query[i].isspace()}
            if not any(term in text for term in terms if len(term) > 1):
                continue
        out.append(
            {
                "score": round(score, 4),
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "text": text[:2000],
            }
        )
    return out


def answer(db: Session, user_id: str, question: str, evidence: list[dict]) -> dict:
    if not evidence:
        return {"answer": "没有找到相关记忆，我无法据此回答。", "citations": []}
    context = "\n".join(f"[{i + 1}] {e['text']}" for i, e in enumerate(evidence))
    result = get_llm().generate(
        rag_system(),
        f"问题：{question}\n\n证据片段：\n{context}\n\n请依据证据回答并标注引用编号。",
        temperature=0.3,
    )
    return {"answer": result.text, "citations": evidence, "provider": result.provider, "model": result.model}
