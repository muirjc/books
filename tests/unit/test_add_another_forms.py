"""Spec 004: the next number in a series and the carry-over form (research R4, R5)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from book_tracker.domain import models as domain
from book_tracker.domain.enums import ReadingStatus
from book_tracker.domain.values import format_series_number
from book_tracker.web.forms import carry_over_form, next_series_number

NOW = datetime(2026, 11, 21, tzinfo=UTC)
ME = domain.UserRef(uuid.uuid4(), "Alice")


@pytest.mark.ac("004/AC-09")
@pytest.mark.parametrize(
    ("number", "expected"),
    [("3", "4"), ("4.5", "5"), ("0", "1"), ("12.25", "13"), ("3.00", "4"), (None, None)],
)
def test_next_series_number(number: str | None, expected: str | None) -> None:
    result = next_series_number(Decimal(number) if number is not None else None)
    assert (format_series_number(result) if result is not None else None) == expected


def _entry(
    *,
    authors: tuple[str, ...] = ("Jim Butcher",),
    series: str | None = "The Dresden Files",
    number: str | None = "3",
    status: ReadingStatus = ReadingStatus.FINISHED,
) -> domain.ReadingEntry:
    book = domain.Book(
        id=uuid.uuid4(),
        title="Grave Peril",
        authors=tuple(
            domain.BookAuthor(uuid.uuid4(), name, None, i) for i, name in enumerate(authors)
        ),
        series=domain.SeriesRef(uuid.uuid4(), series) if series else None,
        series_number=Decimal(number) if number is not None else None,
        isbn_13="9780451458445",
        current_summary=None,
        created_by=ME, created_at=NOW, updated_by=ME, updated_at=NOW,
    )  # fmt: skip
    return domain.ReadingEntry(
        id=uuid.uuid4(), book=book, status=status, finished_on=date(2026, 3, 1),
        times_read=1, notes="Private.", created_at=NOW, updated_at=NOW,
    )  # fmt: skip


@pytest.mark.ac("004/AC-07")
@pytest.mark.ac("004/AC-08")
@pytest.mark.ac("004/AC-09")
@pytest.mark.ac("004/AC-10")
def test_carry_over_form_maps_authors_series_number_status() -> None:
    entry = _entry(authors=("Jim Butcher", "Priscilla Spencer"), status=ReadingStatus.READING)
    raw = carry_over_form(entry).raw
    book = entry.book
    assert book.series is not None
    assert raw == {
        "author_name_0": "Jim Butcher",
        "author_id_0": str(book.authors[0].id),
        "author_name_1": "Priscilla Spencer",
        "author_id_1": str(book.authors[1].id),
        "series_name": "The Dresden Files",
        "series_id": str(book.series.id),
        "series_number": "4",
        "status": "reading",
    }


@pytest.mark.ac("004/AC-09")
def test_carry_over_form_without_series_or_number() -> None:
    no_series = carry_over_form(_entry(series=None, number=None)).raw
    assert "series_name" not in no_series and "series_number" not in no_series
    no_number = carry_over_form(_entry(number=None)).raw
    assert no_number["series_name"] == "The Dresden Files"
    assert "series_number" not in no_number
