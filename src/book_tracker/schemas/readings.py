"""Reading-list schemas (contract components)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator

from book_tracker.domain.enums import ReadingStatus
from book_tracker.schemas.auth import RequestModel
from book_tracker.schemas.catalog import Book, BookCreate, SeriesRef
from book_tracker.schemas.types import FinishedOn, Notes


class ReadingEntryCreate(RequestModel):
    """Exactly one of ``book_id`` (an existing catalog book) or ``new_book``."""

    book_id: uuid.UUID | None = None
    new_book: BookCreate | None = None
    status: ReadingStatus = ReadingStatus.FINISHED
    finished_on: FinishedOn = None
    notes: Notes = None

    @model_validator(mode="after")
    def _one_book(self) -> Self:
        if (self.book_id is None) == (self.new_book is None):
            raise ValueError("Give either book_id or new_book")
        return self


class ReadingEntryUpdate(RequestModel):
    status: ReadingStatus | None = None
    finished_on: FinishedOn = None
    times_read: int | None = Field(default=None, ge=0, le=99)
    notes: Notes = None

    @model_validator(mode="after")
    def _something(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Change at least one field")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status can't be empty")
        if "times_read" in self.model_fields_set and self.times_read is None:
            raise ValueError("times_read can't be empty")
        return self


class ReadingEntry(BaseModel):
    id: uuid.UUID
    book: Book
    status: ReadingStatus
    finished_on: date | None
    times_read: int = Field(ge=0, le=99)
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ReadingEntryPage(BaseModel):
    items: list[ReadingEntry]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class MySeriesView(BaseModel):
    series: SeriesRef
    entries: list[ReadingEntry]
