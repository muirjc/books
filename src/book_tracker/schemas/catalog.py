"""Catalog schemas: authors, series, books and summaries (contract components)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from book_tracker.domain.enums import SummaryOrigin
from book_tracker.domain.values import PEN_NAME_FIRST
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


class SummaryCreate(RequestModel):
    text: SummaryText


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
