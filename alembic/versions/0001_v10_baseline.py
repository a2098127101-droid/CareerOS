"""CareerOS v1.0 baseline schema.

The baseline is materialized from the current versioned schema manifest and is intended for fresh
PostgreSQL/SQLite environments. Existing legacy SQLite databases continue to use forward migrations
until explicitly exported, imported and verified through the v1 repository runtime.
"""
from __future__ import annotations

from alembic import op

from app.core.database import BASELINE_METADATA

revision = "0001_v10_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    BASELINE_METADATA.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    BASELINE_METADATA.drop_all(bind=op.get_bind(), checkfirst=True)
