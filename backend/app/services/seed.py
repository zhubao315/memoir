"""Idempotent seed for prompt categories & the 200-question bank."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.prompts.questions import CATEGORIES, QUESTIONS
from app.models.story import Prompt, PromptCategory


def seed_prompts(db: Session) -> None:
    for i, (key, name, desc) in enumerate(CATEGORIES):
        if not db.query(PromptCategory).filter(PromptCategory.key == key).first():
            db.add(PromptCategory(key=key, name=name, description=desc, sort_order=i))
    db.commit()
    for key, _name, _desc in CATEGORIES:
        existing = {
            q.question
            for q in db.query(Prompt).filter(Prompt.category_key == key, Prompt.is_system.is_(True)).all()
        }
        for question in QUESTIONS[key]:
            if question not in existing:
                db.add(Prompt(category_key=key, question=question, is_system=True, enabled=True))
    db.commit()
