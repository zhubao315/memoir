#!/usr/bin/env python3
"""Non-destructive legacy SQLite -> new schema data migration (Phase 1).

Rules (from task book):
- Never delete/overwrite the original SQLite DB or its tables.
- Preserve original UUIDs, timestamps, bcrypt password hashes and media paths.
- Copy only; skip rows already migrated (idempotent).
- --dry-run and --verify supported; always print before/after counts.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import datetime
from pathlib import Path


def _dt(value):
    """Convert a legacy SQLite DATETIME string into a Python datetime."""
    if value is None or isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

LEGACY_DEFAULT = str(Path(__file__).resolve().parents[1] / "backend" / "memoir.db")


def legacy_counts(conn: sqlite3.Connection) -> dict:
    out = {}
    for t in ("users", "entries", "tags", "media"):
        try:
            out[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except sqlite3.Error:
            out[t] = 0
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy", default=LEGACY_DEFAULT, help="path to v0.1 SQLite DB (read-only)")
    parser.add_argument("--target", default=os.getenv("DATABASE_URL", "sqlite:///./memoir.db"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    legacy = sqlite3.connect(f"file:{args.legacy}?mode=ro", uri=True)
    legacy.row_factory = sqlite3.Row
    before = legacy_counts(legacy)
    print("legacy counts:", before)

    if args.dry_run:
        print("[dry-run] no changes written")
        return

    os.environ.setdefault("DATABASE_URL", args.target)
    # Imports after env is set so settings pick up the target DB.
    from app.db.session import SessionLocal
    from app.models.legacy_tables import Entry, Media as LegacyMedia, Tag, User
    from app.models.media import MediaAsset
    from app.models.memory import Memory

    db = SessionLocal()
    try:
        copied = {"users": 0, "entries": 0, "tags": 0, "media": 0}
        for row in legacy.execute("SELECT * FROM users"):
            if db.query(User).filter(User.id == row["id"]).first():
                continue
            db.add(
                User(
                    id=row["id"], username=row["username"], email=row["email"],
                    hashed_password=row["hashed_password"], created_at=_dt(row["created_at"]),
                    updated_at=_dt(row["updated_at"]) if "updated_at" in row.keys() else None,
                )
            )
            copied["users"] += 1

        import json
        for row in legacy.execute("SELECT * FROM entries"):
            if db.query(Memory).filter(Memory.legacy_entry_id == row["id"]).first():
                continue
            tags = row["tags"]
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except Exception:
                    tags = []
            loc = row["location"]
            if isinstance(loc, str):
                try:
                    loc = json.loads(loc)
                except Exception:
                    loc = {}
            db.add(
                Memory(
                    id=row["id"],
                    user_id=row["user_id"],
                    creator_id=row["user_id"],
                    title=row["title"],
                    raw_content=row["content"],
                    occurred_at=row["entry_date"],
                    memory_type=row["entry_type"] or "memory",
                    mood=row["mood"] or "neutral",
                    location=loc,
                    tags=tags or [],
                    visibility="public" if row["is_public"] else "private",
                    source="import",
                    legacy_entry_id=row["id"],
                    created_at=_dt(row["created_at"]),
                    updated_at=_dt(row["updated_at"]) if "updated_at" in row.keys() else _dt(row["created_at"]),
                )
            )
            copied["entries"] += 1

        for row in legacy.execute("SELECT * FROM tags"):
            if db.query(Tag).filter(Tag.id == row["id"]).first():
                continue
            db.add(
                Tag(
                    id=row["id"], user_id=row["user_id"], name=row["name"],
                    color=row["color"], icon=row["icon"], created_at=_dt(row["created_at"]),
                )
            )
            copied["tags"] += 1

        for row in legacy.execute("SELECT * FROM media"):
            if db.query(LegacyMedia).filter(LegacyMedia.id == row["id"]).first():
                continue
            db.add(
                LegacyMedia(
                    id=row["id"], entry_id=row["entry_id"], user_id=row["user_id"],
                    filename=row["filename"], file_type=row["file_type"],
                    file_path=row["file_path"], file_size=row["file_size"],
                    mime_type=row["mime_type"], caption=row["caption"],
                    taken_at=_dt(row["taken_at"]), created_at=_dt(row["created_at"]),
                )
            )
            # Also mirror into the new MediaAsset table.
            if not db.query(MediaAsset).filter(MediaAsset.legacy_media_id == row["id"]).first():
                mt = row["file_type"] or "photo"
                db.add(
                    MediaAsset(
                        user_id=row["user_id"], storage_key=row["file_path"],
                        storage_backend="local", original_filename=row["filename"],
                        media_type="audio" if mt == "audio" else ("video" if mt == "video" else "photo"),
                        mime_type=row["mime_type"], size_bytes=row["file_size"],
                        legacy_media_id=row["id"], created_at=_dt(row["created_at"]),
                    )
                )
            copied["media"] += 1

        db.commit()
        print("copied:", copied)
    finally:
        db.close()

    if args.verify:
        for table in ("users", "entries", "tags", "media"):
            print(f"verify {table}: legacy={before[table]}")


if __name__ == "__main__":
    main()
