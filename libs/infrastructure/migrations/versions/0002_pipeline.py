"""snapshots, changes, and outbox tables.

Revision ID: 0002_pipeline
Revises: 0001_initial
Create Date: 2026-06-27 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_pipeline"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "url_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("urls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content_ref", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_snapshots_url", "snapshots", ["url_id", "fetched_at"])

    op.create_table(
        "changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "url_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("urls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "previous_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("snapshots.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "new_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("diff_ref", sa.Text(), nullable=True),
        sa.Column(
            "added_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "removed_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("semantic_score", sa.Float(), nullable=True),
        sa.Column(
            "significant",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_changes_url", "changes", ["url_id", "created_at"])

    op.create_table(
        "outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            unique=True,
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_index(
        "idx_outbox_unsent",
        "outbox",
        ["created_at"],
        postgresql_where=sa.text("sent_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_outbox_unsent", table_name="outbox")
    op.drop_table("outbox")
    op.drop_index("idx_changes_url", table_name="changes")
    op.drop_table("changes")
    op.drop_index("idx_snapshots_url", table_name="snapshots")
    op.drop_table("snapshots")
