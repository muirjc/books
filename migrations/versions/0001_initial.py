"""Initial schema: accounts, sessions, sign-in throttle, catalog and reading entries.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-18
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

UUID = postgresql.UUID(as_uuid=True)
NOW = sa.text("now()")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    ]


def _audit(table: str) -> list[sa.Column]:
    return [
        sa.Column(
            "created_by",
            UUID,
            sa.ForeignKey("app_user.id", ondelete="RESTRICT", name=f"{table}_created_by_fkey"),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            UUID,
            sa.ForeignKey("app_user.id", ondelete="RESTRICT", name=f"{table}_updated_by_fkey"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("login", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(10), nullable=False, server_default="member"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        *_timestamps(),
        sa.CheckConstraint("role IN ('member', 'admin')", name="app_user_role_check"),
    )
    op.create_index("app_user_login_lower_uq", "app_user", [sa.text("lower(login)")], unique=True)

    op.create_table(
        "user_session",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("app_user.id", ondelete="CASCADE", name="user_session_user_id_fkey"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.CHAR(64), nullable=False),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("token_hash", name="user_session_token_hash_key"),
    )
    op.create_index("user_session_user_id_idx", "user_session", ["user_id"])

    op.create_table(
        "login_throttle",
        sa.Column("login_key", sa.CHAR(64), primary_key=True),
        sa.Column("failed_count", sa.SmallInteger(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("failed_count >= 0", name="login_throttle_failed_count_check"),
    )

    op.create_table(
        "author",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sort_name", sa.String(200), nullable=False),
        sa.Column("is_pen_name", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("real_name", sa.String(200)),
        *_audit("author"),
        *_timestamps(),
        sa.CheckConstraint(
            "real_name IS NULL OR is_pen_name", name="author_real_name_requires_pen_name"
        ),
    )
    op.create_index("author_name_lower_uq", "author", [sa.text("lower(name)")], unique=True)

    op.create_table(
        "series",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        *_audit("series"),
        *_timestamps(),
    )
    op.create_index("series_name_lower_uq", "series", [sa.text("lower(name)")], unique=True)

    op.create_table(
        "book",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column(
            "series_id",
            UUID,
            sa.ForeignKey("series.id", ondelete="RESTRICT", name="book_series_id_fkey"),
        ),
        sa.Column("series_number", sa.Numeric(5, 2)),
        sa.Column("isbn_13", sa.CHAR(13)),
        *_audit("book"),
        *_timestamps(),
        sa.CheckConstraint(
            "series_number IS NULL OR series_id IS NOT NULL",
            name="book_series_number_requires_series",
        ),
        sa.CheckConstraint(
            "series_number IS NULL OR (series_number >= 0 AND series_number <= 999.99)",
            name="book_series_number_range",
        ),
        sa.CheckConstraint(
            "isbn_13 IS NULL OR isbn_13 ~ '^[0-9]{13}$'", name="book_isbn_13_format"
        ),
        sa.UniqueConstraint("isbn_13", name="book_isbn_13_key"),
    )
    op.create_index(
        "book_series_number_uq",
        "book",
        ["series_id", "series_number"],
        unique=True,
        postgresql_where=sa.text("series_id IS NOT NULL AND series_number IS NOT NULL"),
    )
    op.create_index("book_series_id_idx", "book", ["series_id"])

    op.create_table(
        "book_author",
        sa.Column(
            "book_id",
            UUID,
            sa.ForeignKey("book.id", ondelete="CASCADE", name="book_author_book_id_fkey"),
            primary_key=True,
        ),
        sa.Column(
            "author_id",
            UUID,
            sa.ForeignKey("author.id", ondelete="RESTRICT", name="book_author_author_id_fkey"),
            primary_key=True,
        ),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("position >= 1", name="book_author_position_check"),
        sa.UniqueConstraint("book_id", "position", name="book_author_position_key"),
    )
    op.create_index("book_author_author_id_idx", "book_author", ["author_id"])

    op.create_table(
        "book_summary",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "book_id",
            UUID,
            sa.ForeignKey("book.id", ondelete="CASCADE", name="book_summary_book_id_fkey"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(10), nullable=False),
        sa.Column("model", sa.String(100)),
        sa.Column("source_urls", postgresql.JSONB()),
        sa.Column(
            "created_by",
            UUID,
            sa.ForeignKey("app_user.id", ondelete="RESTRICT", name="book_summary_created_by_fkey"),
            nullable=False,
        ),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.CheckConstraint(
            "origin IN ('ai', 'ai_edited', 'manual')", name="book_summary_origin_check"
        ),
        sa.CheckConstraint(
            "origin = 'manual' OR model IS NOT NULL", name="book_summary_ai_model_check"
        ),
    )
    op.create_index(
        "book_summary_current_uq",
        "book_summary",
        ["book_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )

    op.create_table(
        "reading_entry",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("app_user.id", ondelete="RESTRICT", name="reading_entry_user_id_fkey"),
            nullable=False,
        ),
        sa.Column(
            "book_id",
            UUID,
            sa.ForeignKey("book.id", ondelete="RESTRICT", name="reading_entry_book_id_fkey"),
            nullable=False,
        ),
        sa.Column("status", sa.String(15), nullable=False, server_default="finished"),
        sa.Column("finished_on", sa.Date()),
        sa.Column("times_read", sa.SmallInteger(), nullable=False),
        sa.Column("notes", sa.Text()),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('want_to_read', 'reading', 'finished')", name="reading_entry_status_check"
        ),
        sa.CheckConstraint(
            "finished_on IS NULL OR finished_on >= DATE '1900-01-01'",
            name="reading_entry_finished_on_check",
        ),
        sa.CheckConstraint("times_read BETWEEN 0 AND 99", name="reading_entry_times_read_check"),
        sa.UniqueConstraint("user_id", "book_id", name="reading_entry_user_book_key"),
    )
    op.create_index("reading_entry_user_id_idx", "reading_entry", ["user_id"])
    op.create_index("reading_entry_book_id_idx", "reading_entry", ["book_id"])


def downgrade() -> None:
    # Reverse dependency order. Indexes and constraints are dropped with their tables.
    for table in (
        "reading_entry",
        "book_summary",
        "book_author",
        "book",
        "series",
        "author",
        "login_throttle",
        "user_session",
        "app_user",
    ):
        op.drop_table(table)
