"""Schemas for importing an author's books (spec 002 contracts/openapi.yaml)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from book_tracker.domain.enums import ReadingStatus
from book_tracker.domain.imports import MAX_WORKS_PER_IMPORT, SkipReason, WorkState
from book_tracker.schemas.auth import RequestModel

AuthorKey = Annotated[str, StringConstraints(pattern=r"^OL[0-9]+A$", max_length=40)]
WorkKey = Annotated[str, StringConstraints(pattern=r"^OL[0-9]+W$", max_length=40)]
SearchText = Annotated[str, StringConstraints(min_length=1, max_length=200)]
WorksSort = Literal["title", "year"]


class AuthorCandidate(BaseModel):
    author_key: str
    name: str
    birth_date: str | None
    death_date: str | None
    top_work: str | None
    work_count: int = Field(ge=0)


class AuthorCandidateList(BaseModel):
    authors: list[AuthorCandidate]


class WorkCandidate(BaseModel):
    work_key: str
    title: str
    first_publish_year: int | None
    author_names: list[str]
    state: WorkState
    book_id: uuid.UUID | None


class WorkList(BaseModel):
    author: AuthorCandidate
    works: list[WorkCandidate]
    total: int = Field(ge=0)
    truncated: bool
    fetched_at: datetime


class ImportRequest(RequestModel):
    author_key: AuthorKey
    work_keys: list[WorkKey] = Field(min_length=1, max_length=MAX_WORKS_PER_IMPORT)
    status: ReadingStatus = ReadingStatus.FINISHED

    @field_validator("work_keys")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Each book can be listed once")
        return value


class ImportedBook(BaseModel):
    book_id: uuid.UUID
    title: str
    entry_id: uuid.UUID
    new_to_catalog: bool


class SkippedBook(BaseModel):
    book_id: uuid.UUID
    title: str
    reason: SkipReason


class ImportResult(BaseModel):
    added: list[ImportedBook]
    skipped: list[SkippedBook]


class WorksViewForm(BaseModel):
    """Page-route query and form values; blank boxes mean "not given" (review finding 9)."""

    sort: WorksSort = "title"
    q: SearchText | None = None

    @field_validator("sort", "q", mode="before")
    @classmethod
    def _blank_is_absent(cls, value: object, info: object) -> object:
        if isinstance(value, str) and not value.strip():
            return "title" if getattr(info, "field_name", "") == "sort" else None
        return value.strip() if isinstance(value, str) else value


class ImportPageForm(BaseModel):
    """The status and ticks posted by the works page, checked like ``ImportRequest``.

    The counts (none ticked, over 500) are left to the service so the page shows its
    messages; everything else is refused here (review finding 6).
    """

    status: ReadingStatus = ReadingStatus.FINISHED
    work: list[WorkKey] = Field(default_factory=list)
