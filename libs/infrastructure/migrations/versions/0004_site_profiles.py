"""site_profiles table for L2 template fingerprint and zone selector storage.

Revision ID: 0004_site_profiles
Revises: 0003_notifications
Create Date: 2026-06-27 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_site_profiles"
down_revision: str | None = "0003_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("url_pattern", sa.Text(), nullable=False),
        sa.Column("template_hash", sa.Text(), nullable=True),
        sa.Column("template_class", sa.Text(), nullable=True),
        sa.Column(
            "zone_selectors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "significance_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "semantic_threshold",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.05"),
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
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
    op.create_index(
        "idx_site_profiles_domain_pattern",
        "site_profiles",
        ["domain", "url_pattern"],
    )
    op.create_index(
        "idx_site_profiles_template_class",
        "site_profiles",
        ["template_class"],
    )


def downgrade() -> None:
    op.drop_index("idx_site_profiles_template_class", table_name="site_profiles")
    op.drop_index("idx_site_profiles_domain_pattern", table_name="site_profiles")
    op.drop_table("site_profiles")
