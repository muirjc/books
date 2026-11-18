"""Form parsing for the pages. Values go through the same Pydantic types and models as the
JSON API (Constitution Principle VII); this module only turns form fields into them and
collects friendly, per-field error messages."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import TypeAdapter, ValidationError
from starlette.datastructures import FormData

from book_tracker.domain.enums import ReadingStatus
from book_tracker.schemas.readings import ReadingEntryUpdate
from book_tracker.schemas.types import (
    FinishedOn,
    Isbn13In,
    Notes,
    OptionalSummary,
    SeriesNumberIn,
)

MAX_AUTHOR_ROWS = 5

_series_number = TypeAdapter(SeriesNumberIn)
_isbn = TypeAdapter(Isbn13In)
_finished_on = TypeAdapter(FinishedOn)
_notes = TypeAdapter(Notes)
_summary = TypeAdapter(OptionalSummary)


def text(form: FormData, name: str) -> str:
    value = form.get(name)
    return value.strip() if isinstance(value, str) else ""


def optional_uuid(form: FormData, name: str) -> uuid.UUID | None:
    raw = text(form, name)
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def first_error(exc: ValidationError) -> str:
    return str(exc.errors()[0]["msg"]).removeprefix("Value error, ")


@dataclass
class AuthorRow:
    index: int
    author_id: uuid.UUID | None
    name: str


@dataclass
class AddBookForm:
    """The add-book form, parsed. ``errors`` maps field names to messages."""

    book_id: uuid.UUID | None = None
    title: str = ""
    authors: list[AuthorRow] = field(default_factory=list)
    series_id: uuid.UUID | None = None
    series_name: str = ""
    series_number: Decimal | None = None
    isbn_13: str | None = None
    status: ReadingStatus = ReadingStatus.FINISHED
    finished_on: date | None = None
    notes: str | None = None
    summary: str | None = None
    raw: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def chosen_authors(self) -> list[AuthorRow]:
        return [row for row in self.authors if row.author_id or row.name]


def parse_add_book(form: FormData) -> AddBookForm:
    parsed = AddBookForm(raw={key: text(form, key) for key in form})
    errors = parsed.errors
    parsed.book_id = optional_uuid(form, "book_id")
    parsed.authors = [
        AuthorRow(i, optional_uuid(form, f"author_id_{i}"), text(form, f"author_name_{i}"))
        for i in range(MAX_AUTHOR_ROWS)
    ]
    parsed.series_id = optional_uuid(form, "series_id")
    parsed.series_name = " ".join(text(form, "series_name").split())
    parsed.title = " ".join(text(form, "title").split())

    if parsed.book_id is None:
        if not parsed.title:
            errors["title"] = "Enter a title"
        elif len(parsed.title) > 300:
            errors["title"] = "Keep the title to 300 characters or fewer"
        if not parsed.chosen_authors:
            errors["author_name_0"] = "Enter at least one author"
        try:
            parsed.series_number = _series_number.validate_python(text(form, "series_number"))
        except ValidationError as exc:
            errors["series_number"] = first_error(exc)
        if parsed.series_number is not None and parsed.series_id is None and not parsed.series_name:
            errors["series_number"] = "Choose a series first, or leave the number blank"
        try:
            parsed.isbn_13 = _isbn.validate_python(text(form, "isbn_13"))
        except ValidationError as exc:
            errors["isbn_13"] = first_error(exc)
        try:
            parsed.summary = _summary.validate_python(text(form, "summary") or None)
        except ValidationError:
            errors["summary"] = "Keep the summary to 5,000 characters or fewer"

    _parse_entry_fields(form, parsed, errors)
    return parsed


def _parse_entry_fields(form: FormData, parsed: AddBookForm, errors: dict[str, str]) -> None:
    status = text(form, "status") or ReadingStatus.FINISHED.value
    try:
        parsed.status = ReadingStatus(status)
    except ValueError:
        errors["status"] = "Choose a status"
    try:
        parsed.finished_on = _finished_on.validate_python(text(form, "finished_on") or None)
    except ValidationError as exc:
        errors["finished_on"] = _date_message(exc)
    try:
        parsed.notes = _notes.validate_python(text(form, "notes") or None)
    except ValidationError:
        errors["notes"] = "Keep notes to 10,000 characters or fewer"


def _date_message(exc: ValidationError) -> str:
    message = first_error(exc)
    return message if "future" in message else "Enter a date like 2026-03-01"


def parse_entry_update(
    form: FormData,
) -> tuple[ReadingEntryUpdate | None, dict[str, str], dict[str, Any]]:
    """Fields present in the form become the update; returns (model, errors, raw values)."""
    raw: dict[str, Any] = {}
    for name in ("status", "finished_on", "times_read", "notes"):
        if name in form:
            raw[name] = text(form, name)
    data: dict[str, Any] = {}
    if "status" in raw:
        data["status"] = raw["status"] or None
    if "finished_on" in raw:
        data["finished_on"] = raw["finished_on"] or None
    if "times_read" in raw and raw["times_read"] != "":
        data["times_read"] = raw["times_read"]
    if "notes" in raw:
        data["notes"] = raw["notes"] or None
    try:
        return ReadingEntryUpdate.model_validate(data), {}, raw
    except ValidationError as exc:
        errors: dict[str, str] = {}
        for error in exc.errors():
            name = str(error["loc"][0]) if error["loc"] else "status"
            message = str(error["msg"]).removeprefix("Value error, ")
            if name == "times_read":
                message = "Enter a whole number from 0 to 99"
            elif name == "finished_on" and "future" not in message:
                message = "Enter a date like 2026-03-01"
            elif name == "status":
                message = "Choose a status"
            errors.setdefault(name, message)
        return None, errors, raw
