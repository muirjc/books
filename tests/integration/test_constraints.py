"""T014: rules from data-model.md are enforced by the database (Constitution Principle VI)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError

from tests.conftest import Factory, TestUser


async def violates(app: Any, sql: str, **params: Any) -> None:
    async with app.state.db.engine.connect() as conn:
        # numeric(5,2) overflow raises DataError; every other rule raises IntegrityError.
        with pytest.raises((IntegrityError, DataError)):
            await conn.execute(text(sql), params)
        await conn.rollback()


async def ok(app: Any, sql: str, **params: Any) -> None:
    async with app.state.db.engine.begin() as conn:
        await conn.execute(text(sql), params)


@pytest.fixture
async def actor(factory: Factory) -> TestUser:
    return await factory.user("actor")


AUTHOR_SQL = (
    "INSERT INTO author (id, name, sort_name, is_pen_name, real_name, created_by, updated_by) "
    "VALUES (:id, :name, :name, :pen, :real, :actor, :actor)"
)
BOOK_SQL = (
    "INSERT INTO book (id, title, series_id, series_number, isbn_13, created_by, updated_by) "
    "VALUES (:id, 'T', :series_id, :number, :isbn, :actor, :actor)"
)


def new_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.mark.ac("001/AC-06")
async def test_series_number_requires_series(app: Any, actor: TestUser) -> None:
    await violates(app, BOOK_SQL, id=new_id(), series_id=None, number=2, isbn=None, actor=actor.id)


@pytest.mark.ac("001/AC-18")
async def test_real_name_requires_pen_name(app: Any, actor: TestUser) -> None:
    await violates(app, AUTHOR_SQL, id=new_id(), name="A", pen=False, real="R", actor=actor.id)
    await ok(app, AUTHOR_SQL, id=new_id(), name="B", pen=True, real="R", actor=actor.id)


@pytest.mark.ac("001/AC-16")
async def test_author_name_unique_ignoring_case(app: Any, actor: TestUser) -> None:
    await ok(
        app, AUTHOR_SQL, id=new_id(), name="Robert Galbraith", pen=False, real=None, actor=actor.id
    )
    await violates(
        app, AUTHOR_SQL, id=new_id(), name="robert galbraith", pen=False, real=None, actor=actor.id
    )


@pytest.mark.ac("001/AC-16")
async def test_series_name_unique_ignoring_case(
    app: Any, factory: Factory, actor: TestUser
) -> None:
    await factory.series("Discworld", actor)
    await violates(
        app,
        "INSERT INTO series (id, name, created_by, updated_by) VALUES (:id, 'DISCWORLD', :a, :a)",
        id=new_id(),
        a=actor.id,
    )


@pytest.mark.ac("001/AC-29")
async def test_login_unique_ignoring_case(app: Any, factory: Factory) -> None:
    await factory.user("Sam")
    await violates(
        app,
        "INSERT INTO app_user (id, display_name, login, password_hash) "
        "VALUES (:id, 'x', 'sam', 'h')",
        id=new_id(),
    )


@pytest.mark.ac("001/AC-30")
async def test_isbn_format_and_uniqueness(app: Any, actor: TestUser) -> None:
    await violates(
        app, BOOK_SQL, id=new_id(), series_id=None, number=None, isbn="97803064061", actor=actor.id
    )
    await violates(
        app,
        BOOK_SQL,
        id=new_id(),
        series_id=None,
        number=None,
        isbn="978030640615X",
        actor=actor.id,
    )
    await ok(
        app,
        BOOK_SQL,
        id=new_id(),
        series_id=None,
        number=None,
        isbn="9780306406157",
        actor=actor.id,
    )
    await violates(
        app,
        BOOK_SQL,
        id=new_id(),
        series_id=None,
        number=None,
        isbn="9780306406157",
        actor=actor.id,
    )


@pytest.mark.ac("001/AC-19")
async def test_series_number_unique_within_series(
    app: Any, factory: Factory, actor: TestUser
) -> None:
    series_id = await factory.series("S", actor)
    await ok(app, BOOK_SQL, id=new_id(), series_id=series_id, number=3, isbn=None, actor=actor.id)
    await violates(
        app, BOOK_SQL, id=new_id(), series_id=series_id, number=3, isbn=None, actor=actor.id
    )
    # Books in a series without a number never collide.
    await ok(
        app, BOOK_SQL, id=new_id(), series_id=series_id, number=None, isbn=None, actor=actor.id
    )
    await ok(
        app, BOOK_SQL, id=new_id(), series_id=series_id, number=None, isbn=None, actor=actor.id
    )


@pytest.mark.parametrize("number", [-1, 1000])
async def test_series_number_range(
    app: Any, factory: Factory, actor: TestUser, number: int
) -> None:
    series_id = await factory.series(f"S{number}", actor)
    await violates(
        app, BOOK_SQL, id=new_id(), series_id=series_id, number=number, isbn=None, actor=actor.id
    )


ENTRY_SQL = (
    "INSERT INTO reading_entry (id, user_id, book_id, status, finished_on, times_read) "
    "VALUES (:id, :user, :book, :status, :finished, :times)"
)


@pytest.mark.parametrize("times", [-1, 100])
async def test_times_read_range(app: Any, factory: Factory, actor: TestUser, times: int) -> None:
    book = await factory.book("B", actor)
    await violates(
        app,
        ENTRY_SQL,
        id=new_id(),
        user=actor.id,
        book=book,
        status="finished",
        finished=None,
        times=times,
    )


@pytest.mark.ac("001/AC-05")
async def test_one_entry_per_user_and_book(app: Any, factory: Factory, actor: TestUser) -> None:
    book = await factory.book("B", actor)
    await ok(
        app,
        ENTRY_SQL,
        id=new_id(),
        user=actor.id,
        book=book,
        status="finished",
        finished=None,
        times=1,
    )
    await violates(
        app,
        ENTRY_SQL,
        id=new_id(),
        user=actor.id,
        book=book,
        status="reading",
        finished=None,
        times=0,
    )


async def test_finished_on_lower_bound_and_status_values(
    app: Any, factory: Factory, actor: TestUser
) -> None:
    book = await factory.book("B", actor)
    await violates(
        app,
        ENTRY_SQL,
        id=new_id(),
        user=actor.id,
        book=book,
        status="finished",
        finished="1899-12-31",
        times=1,
    )
    await violates(
        app,
        ENTRY_SQL,
        id=new_id(),
        user=actor.id,
        book=book,
        status="abandoned",
        finished=None,
        times=1,
    )


async def test_role_values(app: Any) -> None:
    await violates(
        app,
        "INSERT INTO app_user (id, display_name, login, password_hash, role) "
        "VALUES (:id, 'x', 'x', 'h', 'owner')",
        id=new_id(),
    )


SUMMARY_SQL = (
    "INSERT INTO book_summary (id, book_id, text, origin, model, created_by, is_current) "
    "VALUES (:id, :book, 'text', :origin, :model, :actor, :current)"
)


async def test_one_current_summary_per_book(app: Any, factory: Factory, actor: TestUser) -> None:
    book = await factory.book("B", actor)
    await ok(
        app,
        SUMMARY_SQL,
        id=new_id(),
        book=book,
        origin="manual",
        model=None,
        actor=actor.id,
        current=True,
    )
    await violates(
        app,
        SUMMARY_SQL,
        id=new_id(),
        book=book,
        origin="manual",
        model=None,
        actor=actor.id,
        current=True,
    )
    await ok(
        app,
        SUMMARY_SQL,
        id=new_id(),
        book=book,
        origin="manual",
        model=None,
        actor=actor.id,
        current=False,
    )


async def test_ai_summary_must_name_model(app: Any, factory: Factory, actor: TestUser) -> None:
    book = await factory.book("B", actor)
    await violates(
        app,
        SUMMARY_SQL,
        id=new_id(),
        book=book,
        origin="ai",
        model=None,
        actor=actor.id,
        current=False,
    )
    await violates(
        app,
        SUMMARY_SQL,
        id=new_id(),
        book=book,
        origin="robot",
        model="m",
        actor=actor.id,
        current=False,
    )


async def test_book_author_position(app: Any, factory: Factory, actor: TestUser) -> None:
    author = await factory.author("A", actor)
    other = await factory.author("O", actor)
    book = await factory.book("B", actor, author_ids=[author])
    sql = "INSERT INTO book_author (book_id, author_id, position) VALUES (:b, :a, :p)"
    await violates(app, sql, b=book, a=other, p=0)
    await violates(app, sql, b=book, a=other, p=1)  # position 1 already used
    await ok(app, sql, b=book, a=other, p=2)
