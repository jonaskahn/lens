"""AI enrichment tables: change_classifications, zone_embeddings.

Revision ID: 0005_ai_enrichment
Revises: 0004_site_profiles
Create Date: 2026-06-27 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_ai_enrichment"
down_revision: str | None = "0004_site_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "change_classifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "change_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("changes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column(
            "is_meaningful",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "severity",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "summary",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "extracted_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.0"),
        ),
        sa.Column(
            "model_id",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "tokens_used",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "llm_latency_ms",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_unique_constraint(
        "uq_change_classifications_change_id",
        "change_classifications",
        ["change_id"],
    )
    op.create_index(
        "idx_change_classifications_change_type",
        "change_classifications",
        ["change_type"],
    )

    op.create_table(
        "zone_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.Text(), nullable=False),
        sa.Column(
            "vector",
            postgresql.ARRAY(postgresql.DOUBLE_PRECISION),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_unique_constraint(
        "uq_zone_embeddings_model_text",
        "zone_embeddings",
        ["model_id", "text_hash"],
    )
    op.create_index(
        "idx_zone_embeddings_model_text",
        "zone_embeddings",
        ["model_id", "text_hash"],
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS zone_embeddings CASCADE")
    op.execute("DROP TABLE IF EXISTS change_classifications CASCADE")
