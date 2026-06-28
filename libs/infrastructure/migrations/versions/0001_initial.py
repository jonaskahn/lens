"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-27 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "domains",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("host", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "default_crawl_config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "default_diff_config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "politeness",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "default_routing",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "domain_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("domains.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("crawl_config", postgresql.JSONB(), nullable=True),
        sa.Column("diff_config", postgresql.JSONB(), nullable=True),
        sa.Column("routing", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("domain_id", "name", name="uq_categories_domain_name"),
    )

    op.create_table(
        "urls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "domain_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("domains.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("crawl_config", postgresql.JSONB(), nullable=True),
        sa.Column("diff_config", postgresql.JSONB(), nullable=True),
        sa.Column("routing", postgresql.JSONB(), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'idle'"),
        ),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "next_due_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_hash", sa.Text(), nullable=True),
        sa.Column(
            "consecutive_errors",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("locked_by", sa.Text(), nullable=True),
        sa.Column("lock_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("domain_id", "address", name="uq_urls_domain_address"),
        sa.CheckConstraint(
            "status IN ('idle','enqueued','crawling','error','disabled')",
            name="ck_urls_status",
        ),
    )
    op.create_index(
        "idx_urls_due",
        "urls",
        ["next_due_at"],
        postgresql_where=sa.text("status = 'idle' AND enabled"),
    )

    op.create_table(
        "channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("apprise_url_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column(
            "enabled",
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "kind IN ('email','slack','discord','telegram','webhook')",
            name="ck_channels_kind",
        ),
    )

    op.create_table(
        "channel_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "channel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "on_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "on_error",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "on_no_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "scope IN ('global','domain','category','url')",
            name="ck_channel_bindings_scope",
        ),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "scopes",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{read}'"),
        ),
        sa.Column(
            "enabled",
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


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_table("channel_bindings")
    op.drop_table("channels")
    op.drop_index("idx_urls_due", table_name="urls")
    op.drop_table("urls")
    op.drop_table("categories")
    op.drop_table("domains")
