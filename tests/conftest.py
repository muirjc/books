"""Shared test infrastructure (task T011).

PostgreSQL comes from, in order of preference:

1. ``BOOK_TRACKER_TEST_DATABASE_URL`` (an empty database the tests may own), or
2. a PostgreSQL 16 testcontainer when Docker is available (CI), or
3. a throwaway cluster started with the local ``initdb`` / ``pg_ctl`` binaries.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import socket
import subprocess
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.auth.passwords import hash_password
from book_tracker.main import create_app
from book_tracker.persistence import models
from book_tracker.settings import Settings
from tests.fakes import FakeBookSource

ROOT = Path(__file__).resolve().parent.parent
AC_ID = re.compile(r"^\d{3}/AC-\d{2}$")  # feature number / criterion, e.g. 002/AC-01
TEST_SECRET = "test-secret-key-that-is-at-least-32-characters-long"
DEFAULT_PASSWORD = "password123"


# --------------------------------------------------------------------------- markers


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        for marker in item.iter_markers(name="ac"):
            for ac_id in marker.args:
                if not isinstance(ac_id, str) or not AC_ID.match(ac_id):
                    raise pytest.UsageError(
                        f"{item.nodeid}: ac marker {ac_id!r} must look like '002/AC-01'"
                    )


# --------------------------------------------------------------------------- database


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(  # noqa: S603
            ["docker", "info"],
            capture_output=True,
            timeout=10,
            check=False,  # noqa: S607
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _local_pg_bin() -> Path | None:
    for candidate in sorted(Path("/usr/lib/postgresql").glob("*/bin"), reverse=True):
        if (candidate / "initdb").exists() and (candidate / "pg_ctl").exists():
            return candidate
    return None


@pytest.fixture(scope="session")
def postgres_server_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """URL (psycopg driver) of a server where the tests may create databases."""
    explicit = os.environ.get("BOOK_TRACKER_TEST_DATABASE_URL")
    if explicit:
        yield explicit
        return

    if _docker_available():
        try:
            from testcontainers.community.postgres import PostgresContainer
        except ImportError:  # pragma: no cover - older testcontainers
            from testcontainers.postgres import PostgresContainer

        with PostgresContainer("postgres:16", driver="psycopg") as container:
            yield container.get_connection_url()
        return

    bin_dir = _local_pg_bin()
    if bin_dir is None:
        pytest.exit(
            "No PostgreSQL available: set BOOK_TRACKER_TEST_DATABASE_URL, start Docker, "
            "or install PostgreSQL server binaries.",
            returncode=2,
        )
    data_dir = tmp_path_factory.mktemp("pgdata")
    port = _free_port()
    subprocess.run(  # noqa: S603
        [
            str(bin_dir / "initdb"),
            "-D",
            str(data_dir),
            "-U",
            "postgres",
            "--auth=trust",
            "--encoding=UTF8",
            "--locale=C.UTF-8",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(  # noqa: S603
        [
            str(bin_dir / "pg_ctl"),
            "-D",
            str(data_dir),
            "-l",
            str(data_dir / "server.log"),
            # TCP only: temporary paths can exceed the 107-byte Unix socket limit.
            "-o",
            f"-p {port} -c unix_socket_directories='' -c listen_addresses=127.0.0.1 -c fsync=off",
            "-w",
            "start",
        ],
        check=True,
        capture_output=True,
    )
    try:
        yield f"postgresql+psycopg://postgres@127.0.0.1:{port}/postgres"
    finally:
        subprocess.run(  # noqa: S603
            [str(bin_dir / "pg_ctl"), "-D", str(data_dir), "-m", "immediate", "stop"],
            check=False,
            capture_output=True,
        )


def create_database(server_url: str, name: str) -> str:
    """Create an empty database on the server and return its URL."""
    import psycopg

    plain = server_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(plain, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}"')
        conn.execute(f'CREATE DATABASE "{name}"')
    base, _, _ = server_url.rpartition("/")
    return f"{base}/{name}"


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["database_url"] = database_url
    return cfg


@pytest.fixture(scope="session")
def database_url(postgres_server_url: str) -> str:
    url = create_database(postgres_server_url, f"book_tracker_test_{os.getpid()}")
    command.upgrade(alembic_config(url), "head")
    return url


@pytest.fixture(scope="session")
def settings(database_url: str) -> Settings:
    return Settings(
        database_url=database_url,
        secret_key=TEST_SECRET,  # type: ignore[arg-type]  # pydantic converts str to SecretStr
        environment="test",
    )


@pytest.fixture(scope="session")
def app(settings: Settings) -> Any:
    return create_app(settings)


TABLES = (
    "book_source_ref",
    "source_lookup_cache",
    "reading_entry",
    "book_summary",
    "book_author",
    "book",
    "series",
    "author",
    "user_session",
    "login_throttle",
    "app_user",
)


@pytest.fixture(autouse=True)
async def _clean_database(request: pytest.FixtureRequest) -> None:
    if "app" not in request.fixturenames:
        return
    app = request.getfixturevalue("app")
    async with app.state.db.engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    app.state.clock = lambda: datetime.now(UTC)


# --------------------------------------------------------------------------- clients


def make_client(app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://testserver",
        follow_redirects=False,
    )


@pytest.fixture
async def client(app: Any) -> AsyncIterator[httpx.AsyncClient]:
    async with make_client(app) as c:
        yield c


@pytest.fixture
async def client_factory(app: Any) -> AsyncIterator[Callable[[], httpx.AsyncClient]]:
    clients: list[httpx.AsyncClient] = []

    def factory() -> httpx.AsyncClient:
        c = make_client(app)
        clients.append(c)
        return c

    yield factory
    for c in clients:
        await c.aclose()


async def presession_token(client: httpx.AsyncClient) -> str:
    response = await client.get("/api/v1/auth/csrf")
    assert response.status_code == 200, response.text
    return str(response.json()["csrf_token"])


async def api_login(
    client: httpx.AsyncClient, login: str, password: str = DEFAULT_PASSWORD
) -> httpx.Response:
    token = await presession_token(client)
    return await client.post(
        "/api/v1/auth/login",
        json={"login": login, "password": password},
        headers={"X-CSRF-Token": token},
    )


async def signed_in(
    client: httpx.AsyncClient, user: TestUser, password: str | None = None
) -> httpx.AsyncClient:
    """Sign the client in as ``user`` and attach the session CSRF token to its headers."""
    response = await api_login(client, user.login, password or user.password)
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client


async def ui_csrf(client: httpx.AsyncClient) -> str:
    """CSRF token of the client's current session, for form posts."""
    response = await client.get("/api/v1/me")
    assert response.status_code == 200, response.text
    return str(response.json()["csrf_token"])


# --------------------------------------------------------------------------- factories


@dataclass
class TestUser:
    __test__ = False
    id: uuid.UUID
    login: str
    display_name: str
    password: str
    role: str


_hash_cache: dict[str, str] = {}


def cached_hash(password: str) -> str:
    if password not in _hash_cache:
        _hash_cache[password] = hash_password(password)
    return _hash_cache[password]


class Factory:
    """Inserts rows directly, bypassing the API, for test set-up."""

    def __init__(self, app: Any) -> None:
        self._app = app

    async def _add(self, obj: Any) -> Any:
        session: AsyncSession
        async with self._app.state.db.sessionmaker() as session:
            session.add(obj)
            await session.commit()
        return obj

    async def user(
        self,
        login: str | None = None,
        *,
        role: str = "member",
        password: str = DEFAULT_PASSWORD,
        display_name: str | None = None,
        must_change_password: bool = False,
        is_active: bool = True,
    ) -> TestUser:
        login = login or f"user-{uuid.uuid4().hex[:8]}"
        row = models.AppUser(
            id=uuid.uuid4(),
            display_name=display_name or login.title(),
            login=login,
            password_hash=cached_hash(password),
            role=role,
            is_active=is_active,
            must_change_password=must_change_password,
        )
        await self._add(row)
        return TestUser(row.id, login, row.display_name, password, role)

    async def author(
        self,
        name: str,
        actor: TestUser,
        *,
        is_pen_name: bool = False,
        real_name: str | None = None,
        sort_name: str | None = None,
    ) -> uuid.UUID:
        row = models.Author(
            id=uuid.uuid4(),
            name=name,
            sort_name=sort_name or name,
            is_pen_name=is_pen_name,
            real_name=real_name,
            created_by=actor.id,
            updated_by=actor.id,
        )
        await self._add(row)
        return row.id

    async def series(self, name: str, actor: TestUser) -> uuid.UUID:
        row = models.Series(id=uuid.uuid4(), name=name, created_by=actor.id, updated_by=actor.id)
        await self._add(row)
        return row.id

    async def book(
        self,
        title: str,
        actor: TestUser,
        *,
        author_ids: list[uuid.UUID] | None = None,
        series_id: uuid.UUID | None = None,
        series_number: str | None = None,
        isbn_13: str | None = None,
    ) -> uuid.UUID:
        if author_ids is None:
            author_ids = [await self.author(f"Author of {title}", actor)]
        book_id = uuid.uuid4()
        async with self._app.state.db.sessionmaker() as session:
            session.add(
                models.Book(
                    id=book_id,
                    title=title,
                    series_id=series_id,
                    series_number=Decimal(series_number) if series_number is not None else None,
                    isbn_13=isbn_13,
                    created_by=actor.id,
                    updated_by=actor.id,
                )
            )
            await session.flush()
            for position, author_id in enumerate(author_ids, start=1):
                session.add(
                    models.BookAuthor(book_id=book_id, author_id=author_id, position=position)
                )
            await session.commit()
        return book_id

    async def entry(
        self,
        user: TestUser,
        book_id: uuid.UUID,
        *,
        status: str = "finished",
        finished_on: date | None = None,
        times_read: int | None = None,
        notes: str | None = None,
    ) -> uuid.UUID:
        row = models.ReadingEntry(
            id=uuid.uuid4(),
            user_id=user.id,
            book_id=book_id,
            status=status,
            finished_on=finished_on,
            times_read=times_read if times_read is not None else (1 if status == "finished" else 0),
            notes=notes,
        )
        await self._add(row)
        return row.id

    async def execute(self, sql: str, **params: Any) -> None:
        """Run a write statement and commit it."""
        async with self._app.state.db.sessionmaker() as session:
            await session.execute(text(sql), params)
            await session.commit()

    async def scalar(self, sql: str, **params: Any) -> Any:
        async with self._app.state.db.sessionmaker() as session:
            return (await session.execute(text(sql), params)).scalar()


@pytest.fixture
def factory(app: Any) -> Factory:
    return Factory(app)


@pytest.fixture
def book_source(app: Any) -> Iterator[FakeBookSource]:
    """Swap in a fake Open Library for one test (spec 002, research R14)."""
    previous = app.state.book_source
    fake = FakeBookSource()
    app.state.book_source = fake
    try:
        yield fake
    finally:
        app.state.book_source = previous


async def gather(*aws: Awaitable[Any]) -> list[Any]:
    return list(await asyncio.gather(*aws))
