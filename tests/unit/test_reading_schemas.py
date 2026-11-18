"""T046: request validation for adding and editing reading entries."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from book_tracker.domain.enums import ReadingStatus
from book_tracker.schemas.catalog import BookCreate
from book_tracker.schemas.readings import ReadingEntryCreate, ReadingEntryUpdate

AUTHOR = str(uuid.uuid4())


def fields(exc: pytest.ExceptionInfo[ValidationError]) -> set[str]:
    return {".".join(str(p) for p in e["loc"]) for e in exc.value.errors()}


def test_exactly_one_of_book_id_and_new_book() -> None:
    with pytest.raises(ValidationError):
        ReadingEntryCreate.model_validate({})
    with pytest.raises(ValidationError):
        ReadingEntryCreate.model_validate(
            {
                "book_id": str(uuid.uuid4()),
                "new_book": {"title": "T", "author_ids": [AUTHOR]},
            }
        )
    assert ReadingEntryCreate.model_validate({"book_id": str(uuid.uuid4())}).new_book is None
    created = ReadingEntryCreate.model_validate(
        {"new_book": {"title": "T", "author_ids": [AUTHOR]}}
    )
    assert created.book_id is None


def test_status_defaults_to_finished() -> None:
    entry = ReadingEntryCreate.model_validate({"book_id": str(uuid.uuid4())})
    assert entry.status is ReadingStatus.FINISHED


@pytest.mark.ac("001/AC-31")
def test_finished_on_not_in_future() -> None:
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError) as exc:
        ReadingEntryCreate.model_validate({"book_id": str(uuid.uuid4()), "finished_on": tomorrow})
    assert "finished_on" in fields(exc)
    with pytest.raises(ValidationError):
        ReadingEntryUpdate.model_validate({"finished_on": tomorrow})
    ReadingEntryUpdate.model_validate({"finished_on": date.today().isoformat()})


def test_notes_limit() -> None:
    with pytest.raises(ValidationError):
        ReadingEntryCreate.model_validate({"book_id": str(uuid.uuid4()), "notes": "x" * 10001})
    ReadingEntryCreate.model_validate({"book_id": str(uuid.uuid4()), "notes": "x" * 10000})


@pytest.mark.ac("001/AC-06")
def test_series_number_requires_series() -> None:
    with pytest.raises(ValidationError) as exc:
        BookCreate.model_validate({"title": "T", "author_ids": [AUTHOR], "series_number": "2"})
    assert fields(exc) == {"series_number"}
    book = BookCreate.model_validate(
        {
            "title": "T",
            "author_ids": [AUTHOR],
            "series_id": str(uuid.uuid4()),
            "series_number": "2.5",
        }
    )
    assert book.series_number == Decimal("2.5")


def test_book_needs_an_author_and_title() -> None:
    with pytest.raises(ValidationError):
        BookCreate.model_validate({"title": "T", "author_ids": []})
    with pytest.raises(ValidationError):
        BookCreate.model_validate({"title": "   ", "author_ids": [AUTHOR]})
    with pytest.raises(ValidationError):
        BookCreate.model_validate({"title": "T", "author_ids": [AUTHOR, AUTHOR]})


def test_update_needs_a_field_and_bounds_times_read() -> None:
    with pytest.raises(ValidationError):
        ReadingEntryUpdate.model_validate({})
    with pytest.raises(ValidationError):
        ReadingEntryUpdate.model_validate({"times_read": 100})
    assert ReadingEntryUpdate.model_validate({"notes": None}).model_fields_set == {"notes"}


def test_unknown_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        ReadingEntryCreate.model_validate({"book_id": str(uuid.uuid4()), "user_id": AUTHOR})
