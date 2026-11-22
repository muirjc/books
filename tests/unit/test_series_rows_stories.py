"""Spec 009: stories on the series page rows, with my derived status (research R3, R4)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from book_tracker.domain import models as domain
from book_tracker.domain.enums import ReadingStatus
from book_tracker.services.readings import SeriesRow, series_rows
from tests.unit.test_series_rows import ME, NOW, SERIES, book, numbered


def story(title: str, number: str, *books: domain.Book) -> domain.Story:
    return domain.Story(
        id=uuid.uuid4(), title=title,
        authors=(domain.BookAuthor(uuid.uuid4(), "Jim Butcher", None, 1),),
        series=SERIES, series_number=Decimal(number),
        books=tuple(domain.BookRef(b.id, b.title) for b in books),
        created_by=ME, created_at=NOW, updated_by=ME, updated_at=NOW,
    )  # fmt: skip


def entry(
    of: domain.Book, status: ReadingStatus = ReadingStatus.FINISHED, on: date | None = None
) -> domain.ReadingEntry:
    return domain.ReadingEntry(
        id=uuid.uuid4(), book=of, status=status, finished_on=on, times_read=1, notes=None,
        created_at=NOW, updated_at=NOW,
    )  # fmt: skip


def shown(rows: tuple[SeriesRow, ...]) -> list[str]:
    out: list[str] = []
    for row in rows:
        if row.story is not None:
            out.append(f"story {row.story.title}")
        elif row.book is not None:
            out.append(row.book.title)
        else:
            out.append(
                f"gap {row.first}" if row.first == row.last else f"gap {row.first}-{row.last}"
            )
    return out


SIDE_JOBS = book("Side Jobs")  # in no series here: it holds stories of this one
BRIEF_CASES = book("Brief Cases")


@pytest.mark.ac("009/AC-09")
@pytest.mark.ac("009/AC-10")
def test_stories_sit_at_their_numbers_book_first() -> None:
    one, two = numbered("1", "2")
    unnumbered = book("Omnibus")
    stories = [
        story("Restoration of Faith", "1.5", SIDE_JOBS),
        story("A Story Called Two", "2", SIDE_JOBS),
    ]
    view = series_rows([one, two, unnumbered], [], stories)
    assert shown(view.rows) == [
        "Book 1",
        "story Restoration of Faith",
        "Book 2",
        "story A Story Called Two",
        "Omnibus",
    ]


@pytest.mark.ac("009/AC-11")
def test_story_status_is_my_best_containing_entry() -> None:
    restoration = story("Restoration of Faith", "1.5", SIDE_JOBS, BRIEF_CASES)
    cases = [
        ([], None, None),
        ([entry(SIDE_JOBS, ReadingStatus.WANT_TO_READ)], ReadingStatus.WANT_TO_READ, None),
        (
            [
                entry(SIDE_JOBS, ReadingStatus.WANT_TO_READ),
                entry(BRIEF_CASES, ReadingStatus.READING),
            ],
            ReadingStatus.READING,
            None,
        ),
        (
            [
                entry(SIDE_JOBS, ReadingStatus.FINISHED, date(2024, 1, 2)),
                entry(BRIEF_CASES, ReadingStatus.FINISHED, date(2025, 6, 7)),
            ],
            ReadingStatus.FINISHED,
            date(2025, 6, 7),
        ),
        ([entry(SIDE_JOBS, ReadingStatus.FINISHED)], ReadingStatus.FINISHED, None),
    ]
    for entries, status, on in cases:
        row = next(r for r in series_rows([], entries, [restoration]).rows if r.story)
        assert (row.story_status, row.story_finished_on) == (status, on), entries
        mine = {e.book.id: e for e in entries}
        assert [(ref.title, found) for ref, found in row.story_books] == [
            ("Side Jobs", mine.get(SIDE_JOBS.id)),
            ("Brief Cases", mine.get(BRIEF_CASES.id)),
        ]


@pytest.mark.ac("009/AC-12")
def test_whole_number_stories_fill_gaps_and_fractions_end_runs() -> None:
    books = numbered("1", "8")
    stories = [story("Three", "3", SIDE_JOBS), story("Five and a half", "5.5", SIDE_JOBS)]
    view = series_rows(books, [], stories)
    assert shown(view.rows) == [
        "Book 1",
        "gap 2",
        "story Three",
        "gap 4",
        "gap 5",
        "story Five and a half",
        "gap 6",
        "gap 7",
        "Book 8",
    ]
    # Only stories: gaps up to the highest story number.
    assert shown(series_rows([], [], [story("Two", "2", SIDE_JOBS)]).rows) == [
        "gap 1",
        "story Two",
    ]


@pytest.mark.ac("009/AC-13")
def test_progress_counts_books_and_stories() -> None:
    one, two = numbered("1", "2")
    stories = [
        story("A", "1.5", SIDE_JOBS),
        story("B", "2.5", SIDE_JOBS),
        story("C", "3.5", BRIEF_CASES),
    ]
    view = series_rows([one, two], [entry(one), entry(SIDE_JOBS)], stories)
    assert (view.finished, view.total) == (1, 2)
    assert (view.stories_finished, view.stories_total) == (2, 3)
    plain = series_rows([one], [entry(one)])
    assert (plain.stories_finished, plain.stories_total) == (0, 0)


@pytest.mark.ac("009/AC-14")
def test_a_collection_in_the_series_lists_the_numbers_it_contains() -> None:
    collection = book("Side Jobs (in series)")
    other = book("Unrelated", "3")
    stories = [story("A", "6.5", collection), story("B", "1.5", collection, BRIEF_CASES)]
    rows = {
        row.book.title: row
        for row in series_rows([other, collection], [], stories).rows
        if row.book and not row.story
    }
    assert rows["Side Jobs (in series)"].contains == (Decimal("1.5"), Decimal("6.5"))
    assert rows["Unrelated"].contains == ()
