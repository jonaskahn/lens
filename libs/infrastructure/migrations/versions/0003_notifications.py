"""notification_log table with per-event, per-channel dedup.

Revision ID: 0003_notifications
Revises: 0002_pipeline
Create Date: 2026-06-27 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_notifications"
down_revision: str | None = "0002_pipeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "channel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("event_id", "channel_id", name="uq_notification_log_event_channel"),
        sa.CheckConstraint(
            "status IN ('sent','failed')",
            name="ck_notification_log_status",
        ),
    )
    op.create_index(
        "idx_notification_log_event",
        "notification_log",
        ["event_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_notification_log_event", table_name="notification_log")
    op.drop_table("notification_log")
