"""T013: every migration is reversible (Constitution Principle VI)."""

from __future__ import annotations

import psycopg
from alembic import command

from tests.conftest import alembic_config, create_database

EXPECTED_TABLES = {
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


def _tables(url: str) -> set[str]:
    plain = url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(plain) as conn:
        rows = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
    return {row[0] for row in rows}


def test_upgrade_downgrade_upgrade(postgres_server_url: str) -> None:
    url = create_database(postgres_server_url, "book_tracker_migration_test")
    cfg = alembic_config(url)

    command.upgrade(cfg, "head")
    assert _tables(url) == EXPECTED_TABLES | {"alembic_version"}

    command.downgrade(cfg, "base")
    assert _tables(url) == {"alembic_version"}

    command.upgrade(cfg, "head")
    assert _tables(url) == EXPECTED_TABLES | {"alembic_version"}
