"""Form parsing for the pages. Values go through the same Pydantic types and models as the
JSON API (Constitution Principle VII); this module only turns form fields into them and
collects friendly, per-field error messages."""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import TypeAdapter, ValidationError
from starlette.datastructures import FormData

from book_tracker.domain import models as domain
from book_tracker.domain.enums import ReadingStatus
from book_tracker.domain.values import SERIES_NUMBER_MAX, format_series_number, normalize_name
from book_tracker.schemas.readings import ReadingEntryUpdate
from book_tracker.schemas.types import (
    FinishedOn,
    Isbn13In,
    Notes,
    OptionalSummary,
    ReleaseDateIn,
    SeriesNumberIn,
)

MAX_AUTHOR_ROWS = 20  # the API's limit
MAX_STORY_ROWS = 50  # spec 013: story rows on one Add a book save
# Book fields an edit page remembers as first shown, sent back as "<name>_was" (books-mbx).
SHOWN_FIELDS = ("title", "authors", "series_id", "series_number", "isbn_13", "release_date")
MIN_AUTHOR_ROWS = 3

_series_number = TypeAdapter(SeriesNumberIn)
_isbn = TypeAdapter(Isbn13In)
_finished_on = TypeAdapter(FinishedOn)
_notes = TypeAdapter(Notes)
_summary = TypeAdapter(OptionalSummary)
_release_date = TypeAdapter(ReleaseDateIn)
RELEASE_DATE_ERROR = "Enter a date like 2027-03-01"


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
    # Spec 005: "Add … as a new author" confirms this exact name; "Use …" picks a record.
    confirmed: str = ""
    use_id: uuid.UUID | None = None


@dataclass
class NewName:
    """A typed author or series that isn't in the catalog yet (spec 005): nothing is saved
    until the member confirms it or picks one of the similar catalog records."""

    field: str  # the form field it belongs to: author_name_<i> or series_name
    kind: Literal["author", "series"]
    name: str
    similar: list[tuple[uuid.UUID, str]]

    @property
    def use_field(self) -> str:
        return self._answer_field("use")

    @property
    def confirm_field(self) -> str:
        return self._answer_field("confirm")

    def _answer_field(self, verb: str) -> str:
        if self.field.startswith("story_"):  # spec 013: story_<kind>_name_<i>
            return f"{verb}_story_{self.kind}_{self.field.rsplit('_', 1)[1]}"
        if self.kind == "series":
            return f"{verb}_series"
        return self.field.replace("author_name", f"{verb}_author", 1)


@dataclass
class StoryRow:
    """One story typed on Add a book (spec 013). A blank series or author means the
    book's. ``story_id`` is an existing story chosen with "Use that story" (AC-13); its
    title, number and series are then carried read-only so the checks still see them."""

    index: int
    title: str = ""
    number_text: str = ""
    number: Decimal | None = None
    series_id: uuid.UUID | None = None
    series_name: str = ""
    author_id: uuid.UUID | None = None
    author_name: str = ""
    story_id: uuid.UUID | None = None
    # Spec 005 answers for this row's names.
    author_confirmed: str = ""
    use_author_id: uuid.UUID | None = None
    series_confirmed: str = ""
    use_series_id: uuid.UUID | None = None

    @property
    def is_blank(self) -> bool:
        return self.story_id is None and not (
            self.title or self.number_text or self.series_name or self.author_name
        )

    @property
    def label(self) -> str:
        return f"Story {self.index + 1}"


STORY_FIELDS = (
    "title", "number", "series_name", "series_id", "author_name", "author_id", "id",
)  # fmt: skip
STORY_ANSWERS = ("confirm_story_author", "use_story_author", "confirm_story_series",
                 "use_story_series")  # fmt: skip


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
    release_date: date | None = None  # spec 007, a catalog field
    # The book's values as an edit page first showed them (books-mbx), by field; only
    # fields the form remembered are present.
    shown: dict[str, str] = field(default_factory=dict)
    # Set by keep_unedited: book fields left as shown (kept as stored), and whether any of
    # them had been changed by another member meanwhile.
    kept: set[str] = field(default_factory=set)
    others_kept: bool = False
    status: ReadingStatus = ReadingStatus.FINISHED
    finished_on: date | None = None
    notes: str | None = None
    pre_ordered: bool = False  # spec 007, a personal field
    summary: str | None = None
    # Where a successful save goes (spec 004): My books, or a fresh form for the next book.
    then: Literal["list", "another"] = "list"
    # Spec 005: the series counterparts of AuthorRow.confirmed and AuthorRow.use_id.
    series_confirmed: str = ""
    use_series_id: uuid.UUID | None = None
    # Spec 006: the series page to return to after a successful save (a parsed id only).
    from_series: uuid.UUID | None = None
    raw: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    new_names: dict[str, NewName] = field(default_factory=dict)  # by field (spec 005)
    names_checked: bool = False  # new_name_prompts has run for this form
    anthology: bool = False  # spec 013: "This book is an anthology or collection"
    stories: list[StoryRow] = field(default_factory=list)

    @property
    def filled_stories(self) -> list[StoryRow]:
        """The rows to save: blank rows are ignored (spec 013 AC-07)."""
        return [row for row in self.stories if not row.is_blank]

    @property
    def field_errors(self) -> bool:
        """Errors other than new-name prompts (those answer 409, not 422)."""
        return any(name not in self.new_names for name in self.errors)

    @property
    def chosen_authors(self) -> list[AuthorRow]:
        """Rows with a name. Clearing the name removes the author, even with a stale id."""
        return [row for row in self.authors if row.name]

    @property
    def author_rows(self) -> int:
        """How many author rows to show: every filled one plus one empty, at least three."""
        filled = [
            int(key.rsplit("_", 1)[1])
            for key, value in self.raw.items()
            if key.startswith(("author_name_", "author_id_")) and value
        ]
        return min(MAX_AUTHOR_ROWS, max(MIN_AUTHOR_ROWS, max(filled, default=-1) + 2))


NAME_TOO_LONG = "Keep the name to 200 characters or fewer"


def parse_add_book(form: FormData, *, stories: bool = True) -> AddBookForm:
    """``stories``: read the spec 013 story rows (Add a book only)."""
    parsed = AddBookForm(raw={key: text(form, key) for key in form})
    errors = parsed.errors
    # The last value wins: the hidden field comes first, the clicked button later (R2).
    parsed.then = "another" if text(form, "then") == "another" else "list"
    parsed.book_id = optional_uuid(form, "book_id")
    parsed.from_series = optional_uuid(form, "from_series")
    parsed.authors = [
        AuthorRow(
            i,
            optional_uuid(form, f"author_id_{i}"),
            normalize_name(text(form, f"author_name_{i}")),
            confirmed=normalize_name(text(form, f"confirm_author_{i}")),
            use_id=optional_uuid(form, f"use_author_{i}"),
        )
        for i in range(MAX_AUTHOR_ROWS)
    ]
    parsed.series_confirmed = normalize_name(text(form, "confirm_series"))
    parsed.use_series_id = optional_uuid(form, "use_series")
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
        for row in parsed.chosen_authors:  # the column holds 200 (PR #33 review)
            if len(row.name) > 200:
                errors.setdefault(f"author_name_{row.index}", NAME_TOO_LONG)
        if len(parsed.series_name) > 200:
            errors["series_name"] = NAME_TOO_LONG
        try:
            parsed.series_number = _series_number.validate_python(text(form, "series_number"))
        except ValidationError as exc:
            errors["series_number"] = first_error(exc)
        if parsed.series_number is not None and not parsed.series_name:
            errors["series_number"] = "Choose a series first, or leave the number blank"
        try:
            parsed.isbn_13 = _isbn.validate_python(text(form, "isbn_13"))
        except ValidationError as exc:
            errors["isbn_13"] = first_error(exc)
        parsed.shown = {
            name: text(form, f"{name}_was") for name in SHOWN_FIELDS if f"{name}_was" in form
        }
        try:
            parsed.release_date = _release_date.validate_python(text(form, "release_date") or None)
        except ValidationError:
            errors["release_date"] = RELEASE_DATE_ERROR
        try:
            parsed.summary = _summary.validate_python(text(form, "summary") or None)
        except ValidationError:
            errors["summary"] = "Keep the summary to 5,000 characters or fewer"

    _parse_entry_fields(form, parsed, errors)
    if parsed.book_id is None and stories:
        _parse_stories(form, parsed)
    return parsed


def _story_indexes(form: FormData) -> list[int]:
    found: set[int] = set()
    prefixes = tuple(f"story_{name}_" for name in STORY_FIELDS) + tuple(
        f"{name}_" for name in STORY_ANSWERS
    )
    for key in form:
        if key.startswith(prefixes):
            tail = key.rsplit("_", 1)[1]
            if tail.isascii() and tail.isdigit() and int(tail) < MAX_STORY_ROWS:
                found.add(int(tail))
    return sorted(found)


def story_raw(row: StoryRow) -> dict[str, str]:
    """The row's values as form fields at its (new) index, for redrawing the form."""
    i = row.index
    raw = {
        f"story_title_{i}": row.title,
        f"story_number_{i}": row.number_text,
        f"story_series_name_{i}": row.series_name,
        f"story_series_id_{i}": str(row.series_id or ""),
        f"story_author_name_{i}": row.author_name,
        f"story_author_id_{i}": str(row.author_id or ""),
        f"story_id_{i}": str(row.story_id or ""),
    }
    if row.author_confirmed:
        raw[f"confirm_story_author_{i}"] = row.author_confirmed
    if row.series_confirmed:
        raw[f"confirm_story_series_{i}"] = row.series_confirmed
    return raw


_ROW_KEY = re.compile(
    r"(story_(?:" + "|".join(STORY_FIELDS) + r")|" + "|".join(STORY_ANSWERS) + r")_\d+"
)


def set_story_rows(parsed: AddBookForm, rows: list[StoryRow]) -> None:
    """Renumber ``rows`` from 0 and rewrite their raw form values to match. Only the rows'
    own numbered fields are touched (the spec 009 story form's ``story_id`` is kept)."""
    for key in [k for k in parsed.raw if _ROW_KEY.fullmatch(k)]:
        del parsed.raw[key]
    for i, row in enumerate(rows):
        row.index = i
        parsed.raw.update(story_raw(row))
    parsed.stories = rows


def _parse_stories(form: FormData, parsed: AddBookForm) -> None:
    """Spec 013: the story rows and their checks (AC-07, AC-08, AC-10 to AC-12)."""
    parsed.anthology = text(form, "anthology") == "yes"
    rows: list[StoryRow] = []
    for i in _story_indexes(form):
        number_text = text(form, f"story_number_{i}")
        rows.append(
            StoryRow(
                index=i,
                title=" ".join(text(form, f"story_title_{i}").split()),
                number_text=number_text,
                series_id=optional_uuid(form, f"story_series_id_{i}"),
                series_name=" ".join(text(form, f"story_series_name_{i}").split()),
                author_id=optional_uuid(form, f"story_author_id_{i}"),
                author_name=normalize_name(text(form, f"story_author_name_{i}")),
                story_id=optional_uuid(form, f"story_id_{i}"),
                author_confirmed=normalize_name(text(form, f"confirm_story_author_{i}")),
                use_author_id=optional_uuid(form, f"use_story_author_{i}"),
                series_confirmed=normalize_name(text(form, f"confirm_story_series_{i}")),
                use_series_id=optional_uuid(form, f"use_story_series_{i}"),
            )
        )
    if parsed.anthology and not rows:
        rows.append(StoryRow(index=0))
    set_story_rows(parsed, rows)
    filled = parsed.filled_stories
    if not filled:
        return
    if not parsed.anthology:
        parsed.errors["anthology"] = (
            "Tick “This book is an anthology or collection” to save these stories, or clear them"
        )
        return
    for row in filled:
        _check_story_row(parsed, row)
    _check_story_pairs(parsed, filled)


def _check_story_row(parsed: AddBookForm, row: StoryRow) -> None:
    errors, i, label = parsed.errors, row.index, row.label
    if not row.title:
        errors[f"story_title_{i}"] = f"{label}: Enter the story's title"
    elif len(row.title) > 300:
        errors[f"story_title_{i}"] = f"{label}: Keep the title to 300 characters or fewer"
    try:
        row.number = _series_number.validate_python(row.number_text)
    except ValidationError as exc:
        errors[f"story_number_{i}"] = f"{label}: {first_error(exc)}"
    else:
        if row.number is None:
            errors[f"story_number_{i}"] = f"{label}: Enter the story's number in the series"
    for name, value in (("author", row.author_name), ("series", row.series_name)):
        if len(value) > 200:
            errors[f"story_{name}_name_{i}"] = f"{label}: {NAME_TOO_LONG}"
    if not row.series_name and not parsed.series_name:
        errors[f"story_series_name_{i}"] = (
            f"{label}: Choose a series for this story, or give the book a series"
        )


def _check_story_pairs(parsed: AddBookForm, rows: list[StoryRow]) -> None:
    """AC-12: no two rows at the same series and number; a blank series is the book's."""
    groups: dict[tuple[str, Decimal], list[StoryRow]] = {}
    for row in rows:
        series = row.series_name or parsed.series_name
        if row.number is not None and series:
            groups.setdefault((series.casefold(), row.number), []).append(row)
    for same in groups.values():
        if len(same) < 2:
            continue
        labels = [row.label for row in same]
        named = " and ".join([", ".join(labels[:-1]), labels[-1]])
        series = same[0].series_name or parsed.series_name
        for row in same:
            parsed.errors.setdefault(
                f"story_number_{row.index}", f"{named} have the same number in {series}"
            )


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
    # A hidden "" comes before the checkbox's "yes"; the last value wins (spec 007 R7).
    parsed.pre_ordered = text(form, "pre_ordered") == "yes"


def _date_message(exc: ValidationError) -> str:
    message = first_error(exc)
    return message if "future" in message else "Enter a date like 2026-03-01"


def parse_entry_update(
    form: FormData,
) -> tuple[ReadingEntryUpdate | None, dict[str, str], dict[str, Any]]:
    """Fields present in the form become the update; returns (model, errors, raw values)."""
    raw: dict[str, Any] = {}
    for name in ("status", "finished_on", "times_read", "notes", "pre_ordered"):
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
    if "pre_ordered" in raw:
        data["pre_ordered"] = raw["pre_ordered"] == "yes"
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


def next_series_number(number: Decimal | None) -> Decimal | None:
    """The next whole number after ``number`` (3 -> 4, 4.5 -> 5), or None when there is no
    number or the next one would pass the highest a book can have (R4)."""
    if number is None:
        return None
    following = Decimal(math.floor(number) + 1)
    return following if following <= SERIES_NUMBER_MAX else None


def carry_over_form(entry: domain.ReadingEntry) -> AddBookForm:
    """A fresh add-book form for the next book after ``entry`` (spec 004 R5): the book's
    authors and series (as chosen catalog records), the next number and the entry's status.
    Everything else, including ``book_id``, stays empty."""
    book = entry.book
    raw: dict[str, str] = {}
    for i, author in enumerate(book.authors):
        raw[f"author_name_{i}"] = author.name
        raw[f"author_id_{i}"] = str(author.id)
    if book.series is not None:
        raw["series_name"] = book.series.name
        raw["series_id"] = str(book.series.id)
        number = next_series_number(book.series_number)
        if number is not None:
            raw["series_number"] = format_series_number(number)
    raw["status"] = entry.status.value
    return AddBookForm(status=entry.status, then="another", raw=raw)


def shown_values(book: domain.Book) -> dict[str, str]:
    """The book as an edit page shows it, keyed "<field>_was" (books-mbx)."""
    return {
        "title_was": book.title,
        "authors_was": ",".join(str(author.id) for author in book.authors),
        "series_id_was": str(book.series.id) if book.series else "",
        "series_number_was": (
            format_series_number(book.series_number) if book.series_number is not None else ""
        ),
        "isbn_13_was": book.isbn_13 or "",
        "release_date_was": book.release_date.isoformat() if book.release_date else "",
    }


def book_start_form(book: domain.Book) -> AddBookForm:
    """Add a book starting from a catalog book (spec 006 R3): the book chosen, its details
    shown, status Want to read. With ``book_id`` set, saving adds that book."""
    raw: dict[str, str] = {"book_id": str(book.id), "title": book.title}
    for i, author in enumerate(book.authors):
        raw[f"author_name_{i}"] = author.name
        raw[f"author_id_{i}"] = str(author.id)
    if book.series is not None:
        raw["series_name"] = book.series.name
        raw["series_id"] = str(book.series.id)
        if book.series_number is not None:
            raw["series_number"] = format_series_number(book.series_number)
    if book.release_date is not None:
        raw["release_date"] = book.release_date.isoformat()
    raw["status"] = ReadingStatus.WANT_TO_READ.value
    return AddBookForm(book_id=book.id, status=ReadingStatus.WANT_TO_READ, raw=raw)


def choose_author(form: AddBookForm, author: domain.Author) -> None:
    """Start Add a book with this catalog author chosen (spec 014 AC-14)."""
    form.raw["author_name_0"] = author.name
    form.raw["author_id_0"] = str(author.id)


def series_start_form(series: domain.Series, number: str) -> AddBookForm:
    """Add a book starting from a series and number, as for a gap row (spec 006 R3). An
    invalid number is left blank."""
    raw: dict[str, str] = {"series_name": series.name, "series_id": str(series.id)}
    try:
        value = _series_number.validate_python(number)
    except ValidationError:
        value = None
    if value is not None:
        raw["series_number"] = format_series_number(value)
    raw["status"] = ReadingStatus.WANT_TO_READ.value
    return AddBookForm(status=ReadingStatus.WANT_TO_READ, raw=raw)


# --------------------------------------------------------------------------- stories (spec 009)

STORY_NUMBER_MISSING = "Enter the story's number in the series"


def parse_story(form: FormData) -> tuple[AddBookForm, uuid.UUID | None, uuid.UUID | None]:
    """The Add or Edit story form: the book form's title, author, series and number checks
    (new-name prompts included, spec 005), plus a required series and number. Returns the
    form, a story picked from the title suggestions, and a story chosen with "Add that
    story to this book" (research R5)."""
    # Never a book id, so the book form's field checks always run.
    parsed = parse_add_book(
        FormData([(k, v) for k, v in form.multi_items() if k != "book_id"]), stories=False
    )
    for name in ("isbn_13", "release_date", "summary"):
        parsed.errors.pop(name, None)
    if not parsed.series_name:
        parsed.errors.setdefault("series_name", "Choose a series")
    if parsed.series_number is None:
        parsed.errors.setdefault("series_number", STORY_NUMBER_MISSING)
    return parsed, optional_uuid(form, "story_id"), optional_uuid(form, "use_story")


def _author_raw(authors: tuple[domain.BookAuthor, ...]) -> dict[str, str]:
    raw: dict[str, str] = {}
    for i, author in enumerate(authors):
        raw[f"author_name_{i}"] = author.name
        raw[f"author_id_{i}"] = str(author.id)
    return raw


def story_start_form(book: domain.Book) -> AddBookForm:
    """Add a story to ``book``: its authors and series filled in (AC-02)."""
    raw = _author_raw(book.authors)
    if book.series is not None:
        raw["series_name"] = book.series.name
        raw["series_id"] = str(book.series.id)
    return AddBookForm(raw=raw)


def story_form(story: domain.Story) -> AddBookForm:
    """A story's current details as a filled-in form."""
    raw = _author_raw(story.authors)
    raw.update(
        {
            "title": story.title,
            "series_name": story.series.name,
            "series_id": str(story.series.id),
            "series_number": format_series_number(story.series_number),
        }
    )
    return AddBookForm(raw=raw)
