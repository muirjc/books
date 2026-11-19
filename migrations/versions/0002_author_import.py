"""Author import (spec 002): source links for imported books, and the lookup cache.

Revision ID: 0002_author_import
Revises: 0001_initial
Create Date: 2026-11-19

Downgrading drops ``book_source_ref``, which holds data (imported books stay, only their
source links go). In production, take and check a backup with books-backup.sh first
(data-model.md, Principle VI).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_author_import"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "book_source_ref",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "book_id",
            UUID,
            sa.ForeignKey("book.id", ondelete="CASCADE", name="book_source_ref_book_id_fkey"),
            nullable=False,
        ),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("source_work_id", sa.String(40), nullable=False),
        sa.Column(
            "imported_by",
            UUID,
            sa.ForeignKey(
                "app_user.id", ondelete="RESTRICT", name="book_source_ref_imported_by_fkey"
            ),
            nullable=False,
        ),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("source IN ('open_library')", name="book_source_ref_source_check"),
        sa.CheckConstraint(
            "source <> 'open_library' OR source_work_id ~ '^OL[0-9]+W$'",
            name="book_source_ref_open_library_id_format",
        ),
        sa.UniqueConstraint("source", "source_work_id", name="book_source_ref_source_work_key"),
        sa.UniqueConstraint("book_id", "source", name="book_source_ref_book_source_key"),
    )
    op.create_index("book_source_ref_book_id_idx", "book_source_ref", ["book_id"])

    op.create_table(
        "source_lookup_cache",
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("lookup_key", sa.String(300), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("source", "kind", "lookup_key", name="source_lookup_cache_pkey"),
        sa.CheckConstraint(
            "source IN ('open_library')", name="source_lookup_cache_source_check"
        ),
        sa.CheckConstraint(
            "kind IN ('author_search', 'author_works')", name="source_lookup_cache_kind_check"
        ),
        sa.CheckConstraint("expires_at > fetched_at", name="source_lookup_cache_expiry_check"),
    )
    op.create_index("source_lookup_cache_expires_at_idx", "source_lookup_cache", ["expires_at"])


def downgrade() -> None:
    # Back up first in production (module docstring). Indexes go with their tables.
    op.drop_table("source_lookup_cache")
    op.drop_table("book_source_ref")
