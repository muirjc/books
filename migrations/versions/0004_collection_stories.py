"""Stories in collections (spec 009): catalog stories, their authors, and the books that
contain them.

Revision ID: 0004_collection_stories
Revises: 0003_upcoming_books
Create Date: 2026-11-22

Downgrading drops the three story tables, which hold data. In production, take and check
a backup with books-backup.sh first (plan.md, Principle VI).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_collection_stories"
down_revision: str | None = "0003_upcoming_books"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "story",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column(
            "series_id",
            UUID,
            sa.ForeignKey("series.id", ondelete="RESTRICT", name="story_series_id_fkey"),
            nullable=False,
        ),
        sa.Column("series_number", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "created_by",
            UUID,
            sa.ForeignKey("app_user.id", ondelete="RESTRICT", name="story_created_by_fkey"),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            UUID,
            sa.ForeignKey("app_user.id", ondelete="RESTRICT", name="story_updated_by_fkey"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "series_number >= 0 AND series_number <= 999.99", name="story_series_number_range"
        ),
    )
    op.create_index("story_series_number_uq", "story", ["series_id", "series_number"], unique=True)
    op.create_table(
        "story_author",
        sa.Column(
            "story_id",
            UUID,
            sa.ForeignKey("story.id", ondelete="CASCADE", name="story_author_story_id_fkey"),
            primary_key=True,
        ),
        sa.Column(
            "author_id",
            UUID,
            sa.ForeignKey("author.id", ondelete="RESTRICT", name="story_author_author_id_fkey"),
            primary_key=True,
        ),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("position >= 1", name="story_author_position_check"),
        sa.UniqueConstraint("story_id", "position", name="story_author_position_key"),
    )
    op.create_index("story_author_author_id_idx", "story_author", ["author_id"])
    op.create_table(
        "book_story",
        sa.Column(
            "book_id",
            UUID,
            sa.ForeignKey("book.id", ondelete="CASCADE", name="book_story_book_id_fkey"),
            primary_key=True,
        ),
        sa.Column(
            "story_id",
            UUID,
            sa.ForeignKey("story.id", ondelete="RESTRICT", name="book_story_story_id_fkey"),
            primary_key=True,
        ),
    )
    op.create_index("book_story_story_id_idx", "book_story", ["story_id"])


def downgrade() -> None:
    op.drop_table("book_story")
    op.drop_table("story_author")
    op.drop_table("story")
