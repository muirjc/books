"""AI summary drafts (spec 012): the draft cache, the per-member daily allowance, and Open
Library book descriptions in the source cache.

Revision ID: 0006_summary_drafts
Revises: 0005_favorite_authors
Create Date: 2026-11-23

Downgrading drops summary_draft (a cache) and ai_draft_usage (members' daily counts, kept
30 days), and deletes cached book descriptions. Nothing in the catalog changes.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_summary_drafts"
down_revision: str | None = "0005_favorite_authors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
KIND_CHECK = "source_lookup_cache_kind_check"


def upgrade() -> None:
    op.create_table(
        "summary_draft",
        sa.Column("id", UUID, nullable=False),
        sa.Column("draft_key", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_urls", postgresql.JSONB(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("series_name", sa.String(200), nullable=True),
        sa.Column("series_number", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="summary_draft_pkey"),
        sa.CheckConstraint("length(btrim(text)) > 0", name="summary_draft_text_check"),
        sa.CheckConstraint(
            "series_number IS NULL OR (series_number >= 0 AND series_number <= 999.99)",
            name="summary_draft_series_number_check",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_urls) = 'array'", name="summary_draft_source_urls_check"
        ),
    )
    op.create_index(
        "summary_draft_key_created_idx",
        "summary_draft",
        ["draft_key", sa.text("created_at DESC")],
    )
    op.create_table(
        "ai_draft_usage",
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("app_user.id", ondelete="CASCADE", name="ai_draft_usage_user_id_fkey"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "day", name="ai_draft_usage_pkey"),
        sa.CheckConstraint("count >= 1", name="ai_draft_usage_count_check"),
    )
    op.drop_constraint(KIND_CHECK, "source_lookup_cache", type_="check")
    op.create_check_constraint(
        KIND_CHECK,
        "source_lookup_cache",
        "kind IN ('author_search', 'author_works', 'book_description')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM source_lookup_cache WHERE kind = 'book_description'")
    op.drop_constraint(KIND_CHECK, "source_lookup_cache", type_="check")
    op.create_check_constraint(
        KIND_CHECK, "source_lookup_cache", "kind IN ('author_search', 'author_works')"
    )
    op.drop_table("ai_draft_usage")
    op.drop_index("summary_draft_key_created_idx", table_name="summary_draft")
    op.drop_table("summary_draft")
