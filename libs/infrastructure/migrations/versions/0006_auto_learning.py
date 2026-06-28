"""Auto-learning: change_labels table.

Revision ID: 0006_auto_learning
Revises: 0005_ai_enrichment
Create Date: 2026-06-27 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_auto_learning"
down_revision: str | None = "0005_ai_enrichment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "change_labels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "change_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("changes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "is_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("is_meaningful", sa.Boolean(), nullable=True),
        sa.Column("change_type", sa.Text(), nullable=True),
        sa.Column("labeled_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_unique_constraint(
        "uq_change_labels_change_labeled_by",
        "change_labels",
        ["change_id", "labeled_by"],
    )
    op.create_index(
        "idx_change_labels_change",
        "change_labels",
        ["change_id"],
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS change_labels CASCADE")
