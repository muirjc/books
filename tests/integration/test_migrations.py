"""T013 (spec 001) and T006 (spec 002): every migration is reversible (Principle VI)."""

from __future__ import annotations

import re

import psycopg
from alembic import command

from tests.conftest import alembic_config, create_database

TABLES_0001 = {
    "app_user",
    "user_session",
    "login_throttle",
    "author",
    "series",
    "book",
    "book_author",
    "book_summary",
    "reading_entry",
}
TABLES_0002 = {"book_source_ref", "source_lookup_cache"}
TABLES_0004 = {"story", "story_author", "book_story"}  # spec 009 T001
TABLES_0005 = {"favorite_author"}  # spec 011 T002
TABLES_0006 = {"summary_draft", "ai_draft_usage"}  # spec 012 T006
EXPECTED_TABLES = TABLES_0001 | TABLES_0002 | TABLES_0004 | TABLES_0005 | TABLES_0006
BEFORE_0004 = TABLES_0001 | TABLES_0002

# Constraints spec 002's services rely on by name (data-model.md).
CONSTRAINTS_0002 = {
    "book_source_ref_source_work_key",
    "book_source_ref_book_source_key",
    "book_source_ref_open_library_id_format",
    "book_source_ref_source_check",
    "source_lookup_cache_pkey",
    "source_lookup_cache_source_check",
    "source_lookup_cache_kind_check",
    "source_lookup_cache_expiry_check",
}


def _plain(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


def _tables(url: str) -> set[str]:
    with psycopg.connect(_plain(url)) as conn:
        rows = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
    return {row[0] for row in rows}


def _constraints(url: str) -> set[str]:
    with psycopg.connect(_plain(url)) as conn:
        rows = conn.execute(
            "SELECT conname FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
            "WHERE t.relname IN ('book_source_ref', 'source_lookup_cache')"
        ).fetchall()
    return {row[0] for row in rows}


def _columns(url: str) -> set[tuple[str, str, str, str | None]]:
    """(table, column, nullable, default) for the spec 007 columns."""
    with psycopg.connect(_plain(url)) as conn:
        rows = conn.execute(
            "SELECT table_name, column_name, is_nullable, column_default "
            "FROM information_schema.columns WHERE (table_name, column_name) IN "
            "(('book', 'release_date'), ('reading_entry', 'pre_ordered'))"
        ).fetchall()
    return {(r[0], r[1], r[2], r[3]) for r in rows}


KINDS_0002 = {"author_search", "author_works"}
KINDS_0006 = KINDS_0002 | {"book_description"}  # spec 012 research R3


def _kind_check(url: str) -> set[str]:
    """The kinds source_lookup_cache_kind_check allows."""
    with psycopg.connect(_plain(url)) as conn:
        row = conn.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'source_lookup_cache_kind_check'"
        ).fetchone()
    assert row is not None
    return set(re.findall(r"'(\w+)'", row[0]))


def _indexes(url: str) -> set[str]:
    with psycopg.connect(_plain(url)) as conn:
        rows = conn.execute("SELECT indexname FROM pg_indexes WHERE tablename = 'book'").fetchall()
    return {row[0] for row in rows}


COLUMNS_0003 = {
    ("book", "release_date", "YES", None),
    ("reading_entry", "pre_ordered", "NO", "false"),
}


def test_upgrade_downgrade_upgrade(postgres_server_url: str) -> None:
    url = create_database(postgres_server_url, "book_tracker_migration_test")
    cfg = alembic_config(url)

    command.upgrade(cfg, "head")
    assert _tables(url) == EXPECTED_TABLES | {"alembic_version"}
    assert CONSTRAINTS_0002 <= _constraints(url)
    assert _columns(url) == COLUMNS_0003  # spec 007 T004
    assert "book_release_date_idx" in _indexes(url)

    assert _kind_check(url) == KINDS_0006
    command.downgrade(cfg, "0005_favorite_authors")  # spec 012
    assert _tables(url) == EXPECTED_TABLES - TABLES_0006 | {"alembic_version"}
    assert _kind_check(url) == KINDS_0002
    command.downgrade(cfg, "0004_collection_stories")  # spec 011
    assert _tables(url) == EXPECTED_TABLES - TABLES_0005 - TABLES_0006 | {"alembic_version"}

    command.downgrade(cfg, "0003_upcoming_books")
    assert _tables(url) == BEFORE_0004 | {"alembic_version"}
    assert _columns(url) == COLUMNS_0003

    command.downgrade(cfg, "0002_author_import")
    assert _tables(url) == BEFORE_0004 | {"alembic_version"}
    assert _columns(url) == set()
    assert "book_release_date_idx" not in _indexes(url)

    command.downgrade(cfg, "0001_initial")
    assert _tables(url) == TABLES_0001 | {"alembic_version"}

    command.downgrade(cfg, "base")
    assert _tables(url) == {"alembic_version"}

    command.upgrade(cfg, "head")
    assert _tables(url) == EXPECTED_TABLES | {"alembic_version"}
    assert CONSTRAINTS_0002 <= _constraints(url)
    assert _columns(url) == COLUMNS_0003
