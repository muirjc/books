"""T021: first Admin account created at installation (FR-006, AC-27)."""

from __future__ import annotations

import psycopg
import pytest

from book_tracker import cli
from tests.conftest import TEST_SECRET


@pytest.fixture
def cli_env(database_url: str, monkeypatch: pytest.MonkeyPatch) -> str:
    plain = database_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(plain, autocommit=True) as conn:
        conn.execute(
            "TRUNCATE reading_entry, book_summary, book_author, book, series, author, "
            "user_session, login_throttle, app_user CASCADE"
        )
    monkeypatch.setenv("BOOK_TRACKER_DATABASE_URL", database_url)
    monkeypatch.setenv("BOOK_TRACKER_SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("BOOK_TRACKER_ENVIRONMENT", "test")
    monkeypatch.setenv("BOOK_TRACKER_ADMIN_PASSWORD", "parent-password")
    return plain


def admins(plain: str) -> list[tuple[str, str, bool, bool]]:
    with psycopg.connect(plain) as conn:
        return conn.execute(
            "SELECT login, role, is_active, must_change_password FROM app_user WHERE role = 'admin'"
        ).fetchall()


@pytest.mark.ac("001/AC-27")
def test_creates_exactly_one_admin(cli_env: str) -> None:
    assert cli.main(["create-admin", "--login", "parent", "--display-name", "Parent"]) == 0
    assert admins(cli_env) == [("parent", "admin", True, False)]


@pytest.mark.ac("001/AC-27")
async def test_created_admin_can_sign_in(cli_env: str, client: object) -> None:
    import asyncio

    import httpx

    from tests.conftest import api_login

    # The CLI runs its own event loop, so call it from a worker thread.
    assert (
        await asyncio.to_thread(
            cli.main, ["create-admin", "--login", "parent", "--display-name", "Parent"]
        )
        == 0
    )
    assert isinstance(client, httpx.AsyncClient)
    response = await api_login(client, "parent", "parent-password")
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_second_run_refused(cli_env: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["create-admin", "--login", "parent", "--display-name", "Parent"]) == 0
    assert cli.main(["create-admin", "--login", "other", "--display-name", "Other"]) == 1
    assert "already exists" in capsys.readouterr().err
    assert [row[0] for row in admins(cli_env)] == ["parent"]


def test_if_missing_is_a_no_op_when_admin_exists(cli_env: str) -> None:
    assert cli.main(["create-admin", "--login", "parent", "--display-name", "Parent"]) == 0
    assert (
        cli.main(["create-admin", "--login", "other", "--display-name", "Other", "--if-missing"])
        == 0
    )
    assert [row[0] for row in admins(cli_env)] == ["parent"]


def test_short_password_refused(
    cli_env: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("BOOK_TRACKER_ADMIN_PASSWORD", "short")
    assert cli.main(["create-admin", "--login", "parent", "--display-name", "Parent"]) == 1
    assert "at least 8 characters" in capsys.readouterr().err
    assert admins(cli_env) == []
