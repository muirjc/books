"""T022: ORM → domain mapping (Constitution Principle VII)."""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from book_tracker.domain import models as domain
from book_tracker.domain.enums import ReadingStatus, Role, SummaryOrigin
from book_tracker.persistence import mappers
from book_tracker.persistence import models as orm

T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 2, 1, tzinfo=UTC)


def user(name: str) -> orm.AppUser:
    return orm.AppUser(
        id=uuid.uuid4(),
        display_name=name,
        login=name.lower(),
        password_hash="h",
        role="member",
        is_active=True,
        must_change_password=False,
        created_at=T0,
        updated_at=T0,
    )


def assert_no_orm(value: Any) -> None:
    """No SQLAlchemy model is reachable from a domain object."""
    assert not isinstance(value, orm.Base)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for field in dataclasses.fields(value):
            assert_no_orm(getattr(value, field.name))
    elif isinstance(value, (tuple, list)):
        for item in value:
            assert_no_orm(item)


def test_to_account() -> None:
    row = user("Alice")
    row.role = "admin"
    account = mappers.to_account(row)
    assert account == domain.Account(
        id=row.id,
        display_name="Alice",
        login="alice",
        role=Role.ADMIN,
        is_active=True,
        must_change_password=False,
        password_hash="h",
        created_at=T0,
    )
    assert mappers.to_user_ref(row) == domain.UserRef(id=row.id, display_name="Alice")


def build_book() -> tuple[orm.Book, orm.AppUser, orm.AppUser]:
    alice, ben = user("Alice"), user("Ben")
    second = orm.Author(
        id=uuid.uuid4(),
        name="Second",
        sort_name="Second",
        is_pen_name=False,
        real_name=None,
        created_at=T0,
        updated_at=T0,
    )
    second.created_by_user = alice
    second.updated_by_user = alice
    first = orm.Author(
        id=uuid.uuid4(),
        name="Robert Galbraith",
        sort_name="Galbraith, Robert",
        is_pen_name=True,
        real_name="J.K. Rowling",
        created_at=T0,
        updated_at=T1,
    )
    first.created_by_user = alice
    first.updated_by_user = ben
    series = orm.Series(id=uuid.uuid4(), name="Strike", created_at=T0, updated_at=T0)
    series.created_by_user = alice
    series.updated_by_user = alice
    book = orm.Book(
        id=uuid.uuid4(),
        title="The Cuckoo's Calling",
        series_number=Decimal("1.00"),
        isbn_13="9780306406157",
        created_at=T0,
        updated_at=T1,
    )
    book.series = series
    book.created_by_user = alice
    book.updated_by_user = ben
    # Deliberately out of order: the mapper sorts by position.
    book.author_links = [
        orm.BookAuthor(author=second, position=2),
        orm.BookAuthor(author=first, position=1),
    ]
    old = orm.BookSummary(
        id=uuid.uuid4(),
        book_id=book.id,
        text="Old",
        origin="manual",
        model=None,
        source_urls=None,
        is_current=False,
        created_at=T0,
    )
    old.created_by_user = alice
    current = orm.BookSummary(
        id=uuid.uuid4(),
        book_id=book.id,
        text="Current",
        origin="manual",
        model=None,
        source_urls=None,
        is_current=True,
        created_at=T1,
    )
    current.created_by_user = ben
    book.current_summary = current
    return book, alice, ben


def test_to_book() -> None:
    book, alice, ben = build_book()
    result = mappers.to_book(book)
    assert result.title == "The Cuckoo's Calling"
    assert [a.name for a in result.authors] == ["Robert Galbraith", "Second"]
    assert [a.position for a in result.authors] == [1, 2]
    assert result.authors[0].real_name == "J.K. Rowling"
    assert result.series == domain.SeriesRef(id=book.series.id, name="Strike")
    assert result.series_number == Decimal("1.00")
    assert result.isbn_13 == "9780306406157"
    assert result.current_summary is not None
    assert result.current_summary.text == "Current"
    assert result.current_summary.origin is SummaryOrigin.MANUAL
    assert result.current_summary.created_by.display_name == "Ben"
    assert result.created_by == domain.UserRef(id=alice.id, display_name="Alice")
    assert result.updated_by == domain.UserRef(id=ben.id, display_name="Ben")
    assert (result.created_at, result.updated_at) == (T0, T1)
    assert_no_orm(result)


def test_to_book_without_series_or_summary() -> None:
    book, _, _ = build_book()
    book.series = None
    book.series_number = None
    book.current_summary = None
    result = mappers.to_book(book)
    assert result.series is None
    assert result.series_number is None
    assert result.current_summary is None


def test_to_author_and_series() -> None:
    book, alice, ben = build_book()
    author = mappers.to_author(book.author_links[1].author)
    assert author.is_pen_name and author.real_name == "J.K. Rowling"
    assert author.sort_name == "Galbraith, Robert"
    assert author.updated_by.display_name == "Ben"
    series = mappers.to_series(book.series)
    assert series.name == "Strike"
    assert series.created_by.id == alice.id
    assert_no_orm(author)
    assert_no_orm(series)


def test_to_summary_with_sources() -> None:
    book, _, _ = build_book()
    row = book.current_summary
    assert row is not None
    row.origin = "ai_edited"
    row.model = "model-x"
    row.source_urls = ["https://example.org/a"]
    summary = mappers.to_summary(row)
    assert summary.origin is SummaryOrigin.AI_EDITED
    assert summary.model == "model-x"
    assert summary.source_urls == ("https://example.org/a",)


def test_to_reading_entry() -> None:
    book, alice, _ = build_book()
    row = orm.ReadingEntry(
        id=uuid.uuid4(),
        user_id=alice.id,
        book_id=book.id,
        status="reading",
        finished_on=date(2026, 3, 1),
        times_read=2,
        notes="Private",
        created_at=T0,
        updated_at=T1,
    )
    row.book = book
    entry = mappers.to_reading_entry(row)
    assert entry.status is ReadingStatus.READING
    assert entry.times_read == 2
    assert entry.finished_on == date(2026, 3, 1)
    assert entry.notes == "Private"
    assert entry.book.title == "The Cuckoo's Calling"
    assert_no_orm(entry)
