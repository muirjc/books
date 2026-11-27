"""Reading-list schemas (contract components)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from book_tracker.domain.enums import ReadingStatus
from book_tracker.schemas.auth import RequestModel
from book_tracker.schemas.catalog import (
    MAX_NEW_BOOK_STORIES,
    Book,
    BookCreate,
    NewBookStory,
    SeriesRef,
)
from book_tracker.schemas.types import FinishedOn, Notes


class ReadingEntryCreate(RequestModel):
    """Exactly one of ``book_id`` (an existing catalog book) or ``new_book``."""

    book_id: uuid.UUID | None = None
    new_book: BookCreate | None = None
    status: ReadingStatus = ReadingStatus.FINISHED
    finished_on: FinishedOn = None
    notes: Notes = None
    pre_ordered: bool = False  # spec 007
    stories: list[NewBookStory] | None = Field(
        default=None,
        max_length=MAX_NEW_BOOK_STORIES,
        description="Spec 013: stories in the new book, saved with it; only with new_book",
    )

    @model_validator(mode="after")
    def _one_book(self) -> Self:
        if (self.book_id is None) == (self.new_book is None):
            raise ValueError("Give either book_id or new_book")
        return self

    @field_validator("stories")
    @classmethod
    def _stories_fit_the_book(
        cls, stories: list[NewBookStory] | None, info: ValidationInfo
    ) -> list[NewBookStory] | None:
        """AC-23, AC-24, AC-26: only with a new book; a series for every new story; no
        two items at one series and number, or naming one story twice."""
        if not stories or "new_book" not in info.data:
            return stories  # an invalid new_book reports its own error (PR #33 review)
        new_book = info.data["new_book"]
        if new_book is None:
            raise ValueError("Stories can only be given with new_book")
        seen_pairs: set[tuple[uuid.UUID, object]] = set()
        seen_ids: set[uuid.UUID] = set()
        for i, item in enumerate(stories, start=1):
            if item.story_id is not None:
                if item.story_id in seen_ids:
                    raise ValueError(f"Story {i} repeats an earlier story_id")
                seen_ids.add(item.story_id)
                continue
            if item.series_number is None:
                continue  # spec 019: a story without a series
            series_id = item.series_id or new_book.series_id
            if series_id is None:
                raise ValueError(f"Story {i} needs a series_id: the new book has no series")
            pair = (series_id, item.series_number)
            if pair in seen_pairs:
                raise ValueError(f"Story {i} has the same series and number as an earlier one")
            seen_pairs.add(pair)
        return stories


class ReadingEntryUpdate(RequestModel):
    status: ReadingStatus | None = None
    finished_on: FinishedOn = None
    times_read: int | None = Field(default=None, ge=0, le=99)
    notes: Notes = None
    pre_ordered: bool = False  # spec 007: changed only when given

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
    pre_ordered: bool = Field(description="The owner's own Pre-ordered flag (spec 007)")
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
