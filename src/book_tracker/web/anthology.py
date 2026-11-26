"""Spec 013: an anthology's stories on Add a book.

The rows are parsed in ``web/forms.py``. This module handles the redraw actions (add,
remove, use an existing story), the spec 005 name prompts for the rows, the check for
story numbers already taken, and turning the rows into ``StoryForBook`` items for
``services.readings.add_entry``. See specs/013-anthology-on-add/research.md.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import FormData

from book_tracker.auth.dependencies import Authenticated
from book_tracker.domain import models as domain
from book_tracker.domain.values import format_series_number, similar_names
from book_tracker.services import catalog as catalog_service
from book_tracker.services.catalog import STORY_DELETED, StoryForBook
from book_tracker.services.errors import (
    ConflictError,
    NotFoundError,
    StoryNumberTaken,
    ValidationFailed,
)
from book_tracker.web.forms import (
    MAX_STORY_ROWS,
    AddBookForm,
    NewName,
    StoryRow,
    optional_uuid,
    set_story_rows,
    text,
)

NEW_NAME = "“{}” is not in the family catalog yet"
USE_STORY = re.compile(r"use_story_(\d+)")
Focus = Literal["new", "heading"]


@dataclass
class Redraw:
    """A story action's result: redraw the form (nothing saved) with this focus."""

    focus: Focus | None = None
    status_code: int = 200


def ensure_a_row(form: AddBookForm) -> None:
    """The section always shows at least one row (AC-02)."""
    if not form.stories:
        set_story_rows(form, [StoryRow(index=0)])


def stories_count(raw: str) -> int:
    """A ``stories=N`` query value: 1 to 50, ASCII digits only; anything else is 0."""
    if raw.isascii() and raw.isdigit() and 1 <= int(raw) <= MAX_STORY_ROWS:
        return int(raw)
    return 0


def with_stories(location: str, form: AddBookForm) -> str:
    """Add ``stories=N`` to a success redirect when stories were saved (research R9)."""
    n = len(form.filled_stories) if form.anthology else 0
    if not n:
        return location
    return f"{location}{'&' if '?' in location else '?'}stories={n}"


async def story_action(db: AsyncSession, form: AddBookForm, data: FormData) -> Redraw | None:
    """Add another story, Remove story N, or Use that story (AC-04, AC-05, AC-13): change
    the rows and redraw, writing nothing. None when the post is not one of these."""
    action = text(data, "action")
    rows = form.stories
    use = next(((m, k) for k in data if (m := USE_STORY.fullmatch(k))), None)
    redraw = Redraw()
    if action == "add_story":
        form.anthology = True
        if len(rows) < MAX_STORY_ROWS:
            rows.append(StoryRow(index=len(rows)))
            redraw.focus = "new"
    elif action.startswith("remove_story:"):
        tail = action.split(":", 1)[1]
        if tail.isascii() and tail.isdigit() and int(tail) < len(rows) and len(rows) > 1:
            del rows[int(tail)]
            redraw.focus = "heading"
    elif use is not None:
        match, key = use
        index, story_id = int(match.group(1)), optional_uuid(data, key)
        if index < len(rows) and story_id is not None:
            row = rows[index]
            try:
                story = await catalog_service.get_story(db, story_id)
            except NotFoundError:
                form.errors.clear()
                form.errors[f"story_title_{index}"] = f"{row.label}: {STORY_DELETED}"
                return Redraw(status_code=409)
            _use_story(row, story)
    else:
        return None
    form.errors.clear()  # only the rows changed; the book is checked when it is added
    form.new_names.clear()
    set_story_rows(form, rows)
    return redraw


def _use_story(row: StoryRow, story: domain.Story) -> None:
    row.story_id = story.id
    row.title = story.title
    row.number = story.series_number
    row.number_text = format_series_number(row.number) if row.number is not None else ""
    row.series_id = story.series.id if story.series else None
    row.series_name = story.series.name if story.series else ""
    row.author_id, row.author_name = None, ""


# --------------------------------------------------------------------------- names


@dataclass
class NameState:
    """What the book's names settled, for the rows (research R6): names confirmed or
    already prompted, and "Use …" choices by the typed name (lower-cased)."""

    confirmed: dict[str, set[str]]
    prompted: dict[str, set[str]]
    used: dict[str, dict[str, tuple[uuid.UUID, str]]]

    @classmethod
    def from_book(cls, form: AddBookForm) -> NameState:
        state = cls(
            confirmed={"author": set(), "series": set()},
            prompted={"author": set(), "series": set()},
            used={"author": {}, "series": {}},
        )
        for row in form.chosen_authors:
            if row.confirmed and row.confirmed == row.name:
                state.confirmed["author"].add(row.name.lower())
        if form.series_name and form.series_confirmed == form.series_name:
            state.confirmed["series"].add(form.series_name.lower())
        for prompt in form.new_names.values():
            state.prompted[prompt.kind].add(prompt.name.lower())
        return state


async def _picked(
    db: AsyncSession, kind: str, use_id: uuid.UUID | None, picked_id: uuid.UUID | None, name: str
) -> tuple[uuid.UUID, str] | None:
    """A "Use …" choice, or a picked id whose name still matches what was typed."""
    get = catalog_service.get_author if kind == "author" else catalog_service.get_series
    if use_id is not None:
        try:
            record = await get(db, use_id)
            return record.id, record.name
        except NotFoundError:
            pass
    if picked_id is not None:
        try:
            record = await get(db, picked_id)
        except NotFoundError:
            return None
        if record.name.lower() == name.lower():
            return record.id, record.name
    return None


def _row_name(row: StoryRow, kind: str) -> str:
    return row.author_name if kind == "author" else row.series_name


def _set_row_record(row: StoryRow, kind: str, record: tuple[uuid.UUID, str]) -> None:
    if kind == "author":
        row.author_id, row.author_name = record
    else:
        row.series_id, row.series_name = record


async def story_name_prompts(db: AsyncSession, form: AddBookForm, state: NameState) -> None:
    """Spec 005 prompts for the rows' typed names (AC-15): one prompt per distinct new
    name, on the first field that has it (the book's fields come first)."""
    if not form.anthology:
        return
    candidates: dict[str, catalog_service.Candidates] = {}
    for row in form.filled_stories:
        if row.story_id is not None:
            continue
        for kind in ("author", "series"):
            name = _row_name(row, kind)
            if not name:
                continue
            key = name.lower()
            if key in state.used[kind]:
                _set_row_record(row, kind, state.used[kind][key])
                continue
            use_id = row.use_author_id if kind == "author" else row.use_series_id
            picked_id = row.author_id if kind == "author" else row.series_id
            record = await _picked(db, kind, use_id, picked_id, name)
            if record is not None:
                if record[1].lower() != key:
                    state.used[kind][key] = record
                _set_row_record(row, kind, record)
                continue
            # A stale or mismatched id (deleted, or the name was edited): the name decides.
            if kind == "author":
                row.author_id = None
            else:
                row.series_id = None
            confirmed = row.author_confirmed if kind == "author" else row.series_confirmed
            if confirmed and confirmed == name:
                state.confirmed[kind].add(key)
                continue
            if key in state.confirmed[kind] or key in state.prompted[kind]:
                continue
            named = (
                catalog_service.author_named if kind == "author" else catalog_service.series_named
            )
            if await named(db, name):
                continue
            if kind not in candidates:
                candidates[kind] = await (
                    catalog_service.author_candidates(db)
                    if kind == "author"
                    else catalog_service.series_candidates(db)
                )
            field = f"story_{kind}_name_{row.index}"
            form.new_names[field] = NewName(
                field, kind, name, similar_names(name, candidates[kind])
            )
            form.errors.setdefault(field, f"{row.label}: {NEW_NAME.format(name)}")
            state.prompted[kind].add(key)
    set_story_rows(form, form.stories)  # write chosen records back, so they stick


# --------------------------------------------------------------------------- numbers


BOOK_SERIES = "\0book"  # the cache key for the book's own picked series


async def _existing_series_id(
    db: AsyncSession, form: AddBookForm, row: StoryRow, named: dict[str, uuid.UUID | None]
) -> uuid.UUID | None:
    """The row's series if it is already in the catalog (blank = the book's). ``named``
    caches lookups by lower-cased name."""
    if row.series_name:
        if row.series_id is not None:
            return row.series_id  # settled by story_name_prompts
        name = row.series_name
    elif form.series_name:
        if BOOK_SERIES not in named:  # once per save, not once per row (PR #33 review)
            picked = await _picked(
                db, "series", form.use_series_id, form.series_id, form.series_name
            )
            named[BOOK_SERIES] = picked[0] if picked else None
        if named[BOOK_SERIES] is not None:
            return named[BOOK_SERIES]
        name = form.series_name
    else:
        return None
    if name.lower() not in named:
        named[name.lower()] = await catalog_service.series_id_named(db, name)
    return named[name.lower()]


def mark_taken(
    form: AddBookForm, row: StoryRow, story: domain.Story, taken: dict[int, domain.Story]
) -> None:
    taken[row.index] = story
    number = story.series_number
    place = f"#{format_series_number(number)} " if number is not None else ""
    form.errors[f"story_number_{row.index}"] = (
        f"{row.label}: {place}“{story.title}” is already in the catalog"
    )


async def taken_story_rows(db: AsyncSession, form: AddBookForm) -> dict[int, domain.Story]:
    """Rows whose series and number another story holds (AC-13), checked before anything
    is created, so the member can choose "Use that story". One query for all rows."""
    taken: dict[int, domain.Story] = {}
    if not form.anthology:
        return taken
    named: dict[str, uuid.UUID | None] = {}
    wanted: list[tuple[StoryRow, tuple[uuid.UUID, Decimal]]] = []
    for row in form.filled_stories:
        if row.story_id is not None:  # a chosen story deleted meanwhile (research R5)
            try:
                await catalog_service.get_story(db, row.story_id)
            except NotFoundError:
                form.errors[f"story_title_{row.index}"] = f"{row.label}: {STORY_DELETED}"
            continue
        if row.number is None:
            continue
        series_id = await _existing_series_id(db, form, row, named)
        if series_id is not None:
            wanted.append((row, (series_id, row.number)))
    found = await catalog_service.stories_at(db, [pair for _, pair in wanted])
    for row, pair in wanted:
        if pair in found:
            mark_taken(form, row, found[pair], taken)
    return taken


# --------------------------------------------------------------------------- save


async def _record_id(db: AsyncSession, auth: Authenticated, kind: str, row: StoryRow) -> uuid.UUID:
    """A row's author or series: the settled record, an exact catalog name, or a new one
    (its name was confirmed by ``story_name_prompts``)."""
    picked = row.author_id if kind == "author" else row.series_id
    if picked is not None:
        return picked
    name = _row_name(row, kind)
    named = catalog_service.author_id_named if kind == "author" else catalog_service.series_id_named
    found = await named(db, name)
    if found is None:
        create = (
            catalog_service.create_author if kind == "author" else catalog_service.create_series
        )
        try:
            found = (await create(db, auth.account.id, name=name)).id
        except ConflictError as exc:  # another member added the same name meanwhile
            if exc.existing_id is None:  # pragma: no cover - conflicts always name it
                raise
            found = exc.existing_id
    _set_row_record(row, kind, (found, name))  # a name typed in two rows is created once
    return found


async def stories_to_save(
    db: AsyncSession, auth: Authenticated, form: AddBookForm
) -> list[StoryForBook]:
    """The filled rows as service items, creating confirmed new names (after the book's,
    so a name typed on both is created once)."""
    if not form.anthology:
        return []
    items: list[StoryForBook] = []
    created: dict[tuple[str, str], uuid.UUID] = {}
    for row in form.filled_stories:
        if row.story_id is not None:
            items.append(StoryForBook(story_id=row.story_id))
            continue
        ids: dict[str, uuid.UUID | None] = {}
        for kind in ("author", "series"):
            name = _row_name(row, kind)
            if not name:
                ids[kind] = None
                continue
            key = (kind, name.lower())
            if key not in created:
                created[key] = await _record_id(db, auth, kind, row)
            ids[kind] = created[key]
        author_id = ids["author"]
        items.append(
            StoryForBook(
                title=row.title,
                series_number=row.number,
                series_id=ids["series"],
                author_ids=[author_id] if author_id is not None else None,
            )
        )
    return items


ROW_FIELDS = {"story_id": "story_title", "series_id": "story_series_name",
              "author_ids": "story_author_name", "series_number": "story_number"}  # fmt: skip


def save_errors(
    form: AddBookForm, exc: ValidationFailed | StoryNumberTaken
) -> dict[int, domain.Story] | None:
    """Put a failed save's story errors on their rows (AC-13, AC-16). Returns the taken
    rows for a number conflict, or None when ``exc`` names no story."""
    filled = form.filled_stories
    if isinstance(exc, StoryNumberTaken):
        taken: dict[int, domain.Story] = {}
        mark_taken(form, filled[exc.index], exc.story, taken)
        return taken
    found = False
    for error in exc.errors:
        parts = error.field.split(".")
        if parts[0] != "stories" or len(parts) < 3 or not parts[1].isdigit():
            continue
        row = filled[int(parts[1])]
        field = ROW_FIELDS.get(parts[2], "story_title")
        message = STORY_DELETED if parts[2] == "story_id" else error.message
        form.errors.setdefault(f"{field}_{row.index}", f"{row.label}: {message}")
        found = True
    return {} if found else None
