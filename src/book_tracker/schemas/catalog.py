"""Catalog schemas: authors, series, books and summaries (contract components)."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from book_tracker.domain.enums import SummaryOrigin
from book_tracker.domain.values import PEN_NAME_FIRST, parse_series_number
from book_tracker.schemas.auth import RequestModel
from book_tracker.schemas.types import (
    Isbn13In,
    Name,
    OptionalName,
    OptionalSummary,
    ReleaseDateIn,
    SeriesNumberIn,
    SummaryText,
    Title,
    search_text,
)

# --------------------------------------------------------------------------- output


class UserRef(BaseModel):
    id: uuid.UUID
    display_name: str


class SeriesRef(BaseModel):
    id: uuid.UUID
    name: str


class BookAuthorRef(BaseModel):
    id: uuid.UUID
    name: str
    real_name: str | None
    position: int


class Summary(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    text: str
    origin: SummaryOrigin
    model: str | None
    source_urls: list[str] | None
    is_current: bool
    created_by: UserRef
    created_at: datetime


class Author(BaseModel):
    id: uuid.UUID
    name: str
    sort_name: str
    is_pen_name: bool
    real_name: str | None
    created_by: UserRef
    created_at: datetime
    updated_by: UserRef
    updated_at: datetime


class Series(BaseModel):
    id: uuid.UUID
    name: str
    created_by: UserRef
    created_at: datetime
    updated_by: UserRef
    updated_at: datetime


class Book(BaseModel):
    id: uuid.UUID
    title: str
    authors: list[BookAuthorRef]
    series: SeriesRef | None
    series_number: str | None = Field(
        description='Decimal as a string, e.g. "2.5"', pattern=r"^[0-9]{1,3}(\.[0-9]{1,2})?$"
    )
    isbn_13: str | None
    release_date: date | None = Field(description="Expected or actual release date (spec 007)")
    current_summary: Summary | None
    created_by: UserRef
    created_at: datetime
    updated_by: UserRef
    updated_at: datetime


class BookRef(BaseModel):
    id: uuid.UUID
    title: str


class Story(BaseModel):
    """A story in a series, contained in one or more books (spec 009)."""

    id: uuid.UUID
    title: str
    authors: list[BookAuthorRef]
    series: SeriesRef
    series_number: str = Field(
        description='Decimal as a string, e.g. "2.5"', pattern=r"^[0-9]{1,3}(\.[0-9]{1,2})?$"
    )
    books: list[BookRef] = Field(description="The books that contain it, by title")
    created_by: UserRef
    created_at: datetime
    updated_by: UserRef
    updated_at: datetime


# --------------------------------------------------------------------------- input

AuthorIds = Annotated[list[uuid.UUID], Field(min_length=1, max_length=20)]


def _unique(ids: list[uuid.UUID]) -> list[uuid.UUID]:
    if len(set(ids)) != len(ids):
        raise ValueError("List each author once")
    return ids


class AuthorCreate(RequestModel):
    name: Name
    sort_name: OptionalName = None
    is_pen_name: bool = False
    real_name: OptionalName = None

    @field_validator("real_name")
    @classmethod
    def _pen_name(cls, value: str | None, info: ValidationInfo) -> str | None:
        return _pen_name_rule(value, info)


class SeriesWrite(RequestModel):
    name: Name


class BookCreate(RequestModel):
    title: Title
    author_ids: AuthorIds
    series_id: uuid.UUID | None = None
    series_number: SeriesNumberIn = None
    isbn_13: Isbn13In = None
    release_date: ReleaseDateIn = None
    summary: OptionalSummary = None

    _unique_authors = field_validator("author_ids")(_unique)

    @field_validator("series_number")
    @classmethod
    def _needs_series(cls, value: Decimal | None, info: ValidationInfo) -> Decimal | None:
        if value is not None and info.data.get("series_id") is None:
            raise ValueError("Choose a series first, or leave the number blank")
        return value


def _pen_name_rule(value: str | None, info: ValidationInfo) -> str | None:
    """A real name is only allowed on an author marked as a pen name (FR-014)."""
    if value and not info.data.get("is_pen_name"):
        raise ValueError(PEN_NAME_FIRST)
    return value


class AuthorUpdate(RequestModel):
    """The pen-name rule depends on the stored author, so the service checks it."""

    name: Name | None = None
    sort_name: OptionalName = None
    is_pen_name: bool | None = None
    real_name: OptionalName = None

    @model_validator(mode="after")
    def _something(self) -> Self:
        _require_changes(self, nullable={"real_name"})
        return self


class BookUpdate(RequestModel):
    title: Title | None = None
    author_ids: AuthorIds | None = None
    series_id: uuid.UUID | None = None
    series_number: SeriesNumberIn = None
    isbn_13: Isbn13In = None
    release_date: ReleaseDateIn = None

    _unique_authors = field_validator("author_ids")(
        lambda ids: _unique(ids) if ids is not None else ids
    )

    @model_validator(mode="after")
    def _something(self) -> Self:
        _require_changes(self, nullable={"series_id", "series_number", "isbn_13", "release_date"})
        return self


def _require_changes(model: BaseModel, nullable: set[str]) -> None:
    if not model.model_fields_set:
        raise ValueError("Change at least one field")
    for name in model.model_fields_set - nullable:
        if getattr(model, name) is None:
            raise ValueError(f"{name} can't be empty")


class SummaryDraftRequest(RequestModel):
    """Ask for an AI draft (spec 012); ``regenerate`` bypasses the 30-day cache."""

    regenerate: bool = False


class SeriesSuggestionOut(BaseModel):
    name: str
    number: str | None = Field(
        description='Decimal as a string, e.g. "2.5"', pattern=r"^[0-9]{1,3}(\.[0-9]{1,2})?$"
    )


class SummaryDraft(BaseModel):
    """An unsaved AI draft (spec 012). Save it with ``draft_id`` on the summaries endpoint."""

    id: uuid.UUID
    text: str
    source_urls: list[str]
    model: str
    series_suggestion: SeriesSuggestionOut | None
    cached: bool = Field(description="Drafted earlier and reused; no AI request was made")
    created_at: datetime
    drafts_left_today: int


class SummaryCreate(RequestModel):
    text: SummaryText
    # Spec 012: the AI draft this text came from; any other value saves it as manual.
    draft_id: uuid.UUID | None = None


def _uuid_or_none(value: object) -> str | None:
    """A form's draft id: kept only when it is a UUID; anything else means no draft."""
    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


class SummaryForm(BaseModel):
    """The Summary page's save form (spec 012); ``then`` "series" goes on to Edit book with
    the draft's series suggestion (AC-21)."""

    text: str = ""
    draft_id: str | None = None
    then: Literal["summary", "series"] = "summary"

    @field_validator("then", mode="before")
    @classmethod
    def _then(cls, value: object) -> str:
        return "series" if value == "series" else "summary"

    _draft = field_validator("draft_id", mode="before")(_uuid_or_none)


class SeriesSuggestion(BaseModel):
    """Edit book's ``suggest_series`` and ``suggest_number`` (spec 012 AC-20). Bad values
    are dropped rather than failing: the member checks them before saving anyway."""

    suggest_series: str = ""
    suggest_number: Decimal | None = None

    @field_validator("suggest_series", mode="before")
    @classmethod
    def _name(cls, value: object) -> str:
        return value.replace("\x00", "").strip()[:200] if isinstance(value, str) else ""

    @field_validator("suggest_number", mode="before")
    @classmethod
    def _number(cls, value: object) -> Decimal | None:
        if not isinstance(value, str):
            return None
        try:
            return parse_series_number(value)
        except ValueError:
            return None


class DraftForm(BaseModel):
    """Draft with AI / Regenerate (spec 012): what was in the box, and whether to bypass
    the cache."""

    text: str = Field(default="", max_length=20000)
    regenerate: bool = False

    @field_validator("regenerate", mode="before")
    @classmethod
    def _flag(cls, value: object) -> bool:
        return value in ("1", "true", "on", True)


class StoryAdd(RequestModel):
    """Add an existing story (``story_id``) or a new one (the other four fields) to a book
    (spec 009); not both."""

    story_id: uuid.UUID | None = None
    title: Title | None = None
    author_ids: AuthorIds | None = None
    series_id: uuid.UUID | None = None
    series_number: SeriesNumberIn = None

    _unique_authors = field_validator("author_ids")(
        lambda ids: _unique(ids) if ids is not None else ids
    )

    @model_validator(mode="after")
    def _one_shape(self) -> Self:
        new = {"title", "author_ids", "series_id", "series_number"}
        if self.story_id is not None:
            if self.model_fields_set & new:
                raise ValueError("Give either story_id or a new story's details, not both")
            return self
        missing = sorted(name for name in new if getattr(self, name) is None)
        if missing:
            raise ValueError(f"A new story needs {', '.join(missing)}")
        return self


class StoryUpdate(RequestModel):
    title: Title | None = None
    author_ids: AuthorIds | None = None
    series_id: uuid.UUID | None = None
    series_number: SeriesNumberIn = None

    _unique_authors = field_validator("author_ids")(
        lambda ids: _unique(ids) if ids is not None else ids
    )

    @model_validator(mode="after")
    def _something(self) -> Self:
        _require_changes(self, nullable=set())
        return self


PAGE_RE = re.compile(r"[0-9]{1,6}")


def parse_page(raw: object) -> int:
    """A page number from a query string: ASCII digits, at least 1; anything else is 1."""
    text = raw if isinstance(raw, str) else ""
    return int(text) if PAGE_RE.fullmatch(text) and int(text) >= 1 else 1


CatalogSort = Literal["title", "-title", "author", "series", "-added"]
CATALOG_SORT_VALUES: tuple[str, ...] = get_args(CatalogSort)


class SearchQuery(BaseModel):
    """A page's search text (My books, the type-ahead suggestions): see ``search_text``."""

    model_config = ConfigDict(frozen=True)

    q: str = ""

    @field_validator("q", mode="before")
    @classmethod
    def _q(cls, value: object) -> str:
        return search_text(value)


class CatalogQuery(BaseModel):
    """The Catalog page's query string (spec 010). Bad values fall back to the defaults
    rather than failing, as on My books."""

    model_config = ConfigDict(frozen=True)

    q: str = ""
    sort: CatalogSort = "title"
    not_mine: bool = False
    page: int = Field(default=1, ge=1)

    @field_validator("q", mode="before")
    @classmethod
    def _q(cls, value: object) -> str:
        return search_text(value)

    @field_validator("sort", mode="before")
    @classmethod
    def _sort(cls, value: object) -> str:
        return value if isinstance(value, str) and value in CATALOG_SORT_VALUES else "title"

    @field_validator("not_mine", mode="before")
    @classmethod
    def _not_mine(cls, value: object) -> bool:
        return value is True or value == "1"

    @field_validator("page", mode="before")
    @classmethod
    def _page(cls, value: object) -> int:
        return parse_page(value)


class FavoriteForm(BaseModel):
    """The Author page's favorite button (spec 011): add (yes) or remove (no)."""

    model_config = ConfigDict(frozen=True)

    favorite: Literal["yes", "no"]
