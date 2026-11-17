"""Background worker: polls pending AIJob rows and runs them (ARQ/Celery-ready seam)."""

from __future__ import annotations

import time

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.ai import AIJob
from app.services import tasks


def poll_once() -> int:
    db = SessionLocal()
    try:
        pending = db.query(AIJob).filter(AIJob.status == "pending").order_by(AIJob.created_at.asc()).limit(10).all()
        ids = [job.id for job in pending]
    finally:
        db.close()
    for job_id in ids:
        tasks.run_job(job_id)
    return len(ids)


def main() -> None:
    print(f"[memoir-worker] started; polling every 2s (provider={settings.AI_PROVIDER}, asr={settings.ASR_PROVIDER})", flush=True)
    while True:
        try:
            poll_once()
        except Exception as exc:  # pragma: no cover
            print(f"[memoir-worker] error: {exc}", flush=True)
        time.sleep(2)


if __name__ == "__main__":
    main()
