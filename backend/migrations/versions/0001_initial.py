"""Initial schema: legacy tables + all domain tables (idempotent, non-destructive).

Revision ID: 0001_initial
"""

from __future__ import annotations

from alembic import op
import app.models  # noqa: F401  — registers every table on Base.metadata
from app.db.base import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # checkfirst=True: on an existing v0.1 database only the missing domain tables are
    # created; legacy users/entries/tags/media are left untouched.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # Intentionally a no-op: we never drop legacy tables or user data automatically.
    # A full rollback requires the documented backup-restore procedure.
    pass
