"""T013 (spec 001) and T006 (spec 002): every migration is reversible (Principle VI)."""

from __future__ import annotations

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
EXPECTED_TABLES = TABLES_0001 | TABLES_0002

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


def test_upgrade_downgrade_upgrade(postgres_server_url: str) -> None:
    url = create_database(postgres_server_url, "book_tracker_migration_test")
    cfg = alembic_config(url)

    command.upgrade(cfg, "head")
    assert _tables(url) == EXPECTED_TABLES | {"alembic_version"}
    assert CONSTRAINTS_0002 <= _constraints(url)

    command.downgrade(cfg, "0001_initial")
    assert _tables(url) == TABLES_0001 | {"alembic_version"}

    command.downgrade(cfg, "base")
    assert _tables(url) == {"alembic_version"}

    command.upgrade(cfg, "head")
    assert _tables(url) == EXPECTED_TABLES | {"alembic_version"}
    assert CONSTRAINTS_0002 <= _constraints(url)
