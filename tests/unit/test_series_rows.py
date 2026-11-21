"""Spec 006: the rows of a series page, with my entries and gaps (research R2)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from book_tracker.domain import models as domain
from book_tracker.domain.enums import ReadingStatus
from book_tracker.services.readings import SeriesRow, series_rows

NOW = datetime(2026, 11, 21, tzinfo=UTC)
ME = domain.UserRef(uuid.uuid4(), "Alice")
SERIES = domain.SeriesRef(uuid.uuid4(), "The Dresden Files")


def book(title: str, number: str | None = None) -> domain.Book:
    return domain.Book(
        id=uuid.uuid4(), title=title,
        authors=(domain.BookAuthor(uuid.uuid4(), "Jim Butcher", None, 0),),
        series=SERIES, series_number=Decimal(number) if number is not None else None,
        isbn_13=None, current_summary=None,
        created_by=ME, created_at=NOW, updated_by=ME, updated_at=NOW,
    )  # fmt: skip


def entry(of: domain.Book, status: ReadingStatus = ReadingStatus.FINISHED) -> domain.ReadingEntry:
    return domain.ReadingEntry(
        id=uuid.uuid4(), book=of, status=status,
        finished_on=date(2025, 3, 3) if status is ReadingStatus.FINISHED else None,
        times_read=1, notes=None, created_at=NOW, updated_at=NOW,
    )  # fmt: skip


def shown(rows: tuple[SeriesRow, ...]) -> list[str]:
    """Each row as text: a book's title, or a gap as "gap 3" / "gap 8-499"."""
    out: list[str] = []
    for row in rows:
        if row.book is not None:
            out.append(row.book.title)
        else:
            out.append(
                f"gap {row.first}" if row.first == row.last else f"gap {row.first}-{row.last}"
            )
    return out


def numbered(*numbers: str) -> list[domain.Book]:
    return [book(f"Book {n}", n) for n in numbers]


@pytest.mark.ac("006/AC-01")
@pytest.mark.ac("006/AC-02")
def test_books_keep_order_and_get_my_entry() -> None:
    one, two, side = book("Storm Front", "1"), book("Fool Moon", "2"), book("Side Jobs")
    mine = entry(two, ReadingStatus.READING)
    view = series_rows([one, two, side], [mine])
    assert shown(view.rows) == ["Storm Front", "Fool Moon", "Side Jobs"]
    assert [row.entry for row in view.rows] == [None, mine, None]


@pytest.mark.ac("006/AC-04")
def test_finished_count_and_total_exclude_gaps() -> None:
    books = numbered("1", "2", "5")
    view = series_rows(books, [entry(books[0]), entry(books[1], ReadingStatus.READING)])
    assert (view.finished, view.total) == (1, 3)
    assert shown(view.rows) == ["Book 1", "Book 2", "gap 3", "gap 4", "Book 5"]


def test_entry_for_a_book_not_listed_is_ignored() -> None:
    """An entry whose book has left the series meanwhile doesn't count or show."""
    books = numbered("1")
    stray = entry(book("Moved", "2"))
    view = series_rows(books, [stray])
    assert (view.finished, view.total) == (0, 1)
    assert view.rows[0].entry is None


@pytest.mark.ac("006/AC-15")
def test_no_gaps_without_numbers() -> None:
    view = series_rows([book("B"), book("A")], [])
    assert shown(view.rows) == ["B", "A"]  # catalog order is kept as given


@pytest.mark.ac("006/AC-14")
def test_gaps_with_fractional_numbers() -> None:
    view = series_rows([*numbered("1", "2", "4", "6.5"), book("Side Jobs")], [])
    assert shown(view.rows) == [
        "Book 1", "Book 2", "gap 3", "Book 4", "gap 5", "gap 6", "Book 6.5", "Side Jobs",
    ]  # fmt: skip


@pytest.mark.ac("006/AC-16")
def test_runs_of_three_stay_and_four_collapse() -> None:
    assert shown(series_rows(numbered("1", "5"), []).rows) == [
        "Book 1", "gap 2", "gap 3", "gap 4", "Book 5",
    ]  # fmt: skip
    assert shown(series_rows(numbered("1", "6"), []).rows) == ["Book 1", "gap 2-5", "Book 6"]


@pytest.mark.ac("006/AC-16")
def test_large_top_is_one_row() -> None:
    view = series_rows(numbered("1", "2", "3", "4", "5", "6", "7", "500"), [])
    assert shown(view.rows)[-2:] == ["gap 8-499", "Book 500"]
    assert len(view.rows) == 9


def test_gaps_before_the_first_book() -> None:
    assert shown(series_rows(numbered("3"), []).rows) == ["gap 1", "gap 2", "Book 3"]
    assert shown(series_rows(numbered("0.5", "2"), []).rows) == ["Book 0.5", "gap 1", "Book 2"]


def test_fraction_below_one_makes_no_gap() -> None:
    assert shown(series_rows(numbered("0.5"), []).rows) == ["Book 0.5"]


def test_empty_series() -> None:
    view = series_rows([], [])
    assert (view.rows, view.finished, view.total) == ((), 0, 0)


# --------------------------------------------------------------------------- start forms


@pytest.mark.ac("006/AC-07")
def test_book_start_form() -> None:
    from book_tracker.web.forms import book_start_form

    knight = book("Summer Knight", "4")
    form = book_start_form(knight)
    assert form.book_id == knight.id and form.status is ReadingStatus.WANT_TO_READ
    assert form.raw["title"] == "Summer Knight"
    assert form.raw["author_name_0"] == "Jim Butcher"
    assert form.raw["author_id_0"] == str(knight.authors[0].id)
    assert (form.raw["series_name"], form.raw["series_id"]) == (SERIES.name, str(SERIES.id))
    assert form.raw["series_number"] == "4"
    loose = book_start_form(
        domain.Book(**{**_fields(knight), "series": None, "series_number": None})
    )
    assert "series_name" not in loose.raw and "series_number" not in loose.raw
    unnumbered = book_start_form(book("Side Jobs"))
    assert "series_number" not in unnumbered.raw and unnumbered.raw["series_name"] == SERIES.name


def _fields(of: domain.Book) -> dict[str, object]:
    return {name: getattr(of, name) for name in domain.Book.__slots__}


@pytest.mark.ac("006/AC-09")
@pytest.mark.parametrize(
    ("number", "shown"), [("7", "7"), ("6.50", "6.5"), ("", None), ("abc", None), ("-1", None),
                          ("1000", None)],
)  # fmt: skip
def test_series_start_form(number: str, shown: str | None) -> None:
    from book_tracker.web.forms import series_start_form

    series = domain.Series(SERIES.id, SERIES.name, ME, NOW, ME, NOW)
    form = series_start_form(series, number)
    assert form.book_id is None and form.status is ReadingStatus.WANT_TO_READ
    assert (form.raw["series_name"], form.raw["series_id"]) == (SERIES.name, str(SERIES.id))
    assert form.raw.get("series_number") == shown


def test_parse_from_series() -> None:
    from starlette.datastructures import FormData

    from book_tracker.web.forms import parse_add_book

    assert parse_add_book(FormData([("from_series", str(SERIES.id))])).from_series == SERIES.id
    for bad in ("junk", "https://example.com/", ""):
        assert parse_add_book(FormData([("from_series", bad)])).from_series is None


@pytest.mark.ac("006/AC-14")
def test_fraction_inside_a_long_gap_splits_it() -> None:
    """PR #22 review: a book between missing numbers keeps its place in the order."""
    assert shown(series_rows(numbered("1", "3.5", "7"), []).rows) == [
        "Book 1", "gap 2", "gap 3", "Book 3.5", "gap 4", "gap 5", "gap 6", "Book 7",
    ]  # fmt: skip
    assert shown(series_rows(numbered("1", "2.5", "9"), []).rows) == [
        "Book 1", "gap 2", "Book 2.5", "gap 3-8", "Book 9",
    ]  # fmt: skip
