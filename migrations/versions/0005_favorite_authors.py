"""Favorite authors (spec 011): a member's own favorites, one row per member and author.

Revision ID: 0005_favorite_authors
Revises: 0004_collection_stories
Create Date: 2026-11-22

Downgrading drops favorite_author, which holds members' data. In production, take and check
a backup with books-backup.sh first (plan.md, Principle VI).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_favorite_authors"
down_revision: str | None = "0004_collection_stories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "favorite_author",
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("app_user.id", ondelete="CASCADE", name="favorite_author_user_id_fkey"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            UUID,
            # RESTRICT: a favorited author can't be deleted (constitution 2.0.0, spec 011).
            sa.ForeignKey("author.id", ondelete="RESTRICT", name="favorite_author_author_id_fkey"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("user_id", "author_id", name="favorite_author_pkey"),
    )
    op.create_index("favorite_author_author_id_idx", "favorite_author", ["author_id"])


def downgrade() -> None:
    op.drop_index("favorite_author_author_id_idx", table_name="favorite_author")
    op.drop_table("favorite_author")
