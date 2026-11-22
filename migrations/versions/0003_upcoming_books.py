"""Upcoming books (spec 007): a catalog release date and a personal Pre-ordered flag.

Revision ID: 0003_upcoming_books
Revises: 0002_author_import
Create Date: 2026-11-21

Downgrading drops ``book.release_date`` and ``reading_entry.pre_ordered``, which hold data.
In production, take and check a backup with books-backup.sh first (plan.md, Principle VI).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_upcoming_books"
down_revision: str | None = "0002_author_import"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("book", sa.Column("release_date", sa.Date(), nullable=True))
    op.create_index(
        "book_release_date_idx",
        "book",
        ["release_date"],
        postgresql_where=sa.text("release_date IS NOT NULL"),
    )
    op.add_column(
        "reading_entry",
        sa.Column("pre_ordered", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("reading_entry", "pre_ordered")
    op.drop_index("book_release_date_idx", table_name="book")
    op.drop_column("book", "release_date")
