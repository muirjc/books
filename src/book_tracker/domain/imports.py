"""Domain objects for importing an author's books (spec 002; data-model.md).

Candidates are what Open Library says; they are never catalog content until a member
confirms (FR-007). Plain frozen dataclasses, as in ``domain/models.py`` (Principle VII).
"""

from __future__ import annotations

import enum
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

SOURCE_OPEN_LIBRARY = "open_library"
MAX_WORKS_LISTED = 2000  # FR-020
MAX_WORKS_PER_IMPORT = 500  # FR-014


@dataclass(frozen=True, slots=True)
class AuthorCandidate:
    source_id: str
    name: str
    birth_date: str | None
    death_date: str | None
    top_work: str | None
    work_count: int


@dataclass(frozen=True, slots=True)
class WorkCandidate:
    source_id: str
    alias_ids: tuple[str, ...]  # other Open Library works merged into this one (research R6)
    title: str
    first_publish_year: int | None
    author_names: tuple[str, ...]  # Open Library's order, no repeats
    isbn13s: frozenset[str]  # for matching only, never stored (FR-011)
    edition_count: int

    @property
    def all_ids(self) -> tuple[str, ...]:
        return (self.source_id, *self.alias_ids)


@dataclass(frozen=True, slots=True)
class WorkList:
    author: AuthorCandidate
    works: tuple[WorkCandidate, ...]
    total: int  # Open Library's count for the author
    truncated: bool  # total > MAX_WORKS_LISTED


class WorkState(enum.StrEnum):
    NEW = "new"
    IN_CATALOG = "in_catalog"
    ON_MY_LIST = "on_my_list"


@dataclass(frozen=True, slots=True)
class WorkListing:
    """One work as shown to one member (FR-005)."""

    work: WorkCandidate
    state: WorkState
    book_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class WorksView:
    author: AuthorCandidate
    works: tuple[WorkListing, ...]
    total: int
    truncated: bool
    fetched_at: datetime
    # Every id in the whole list, before filtering, merged ids included → the work's own id.
    lead_ids: Mapping[str, str] = field(default_factory=dict)


class SkipReason(enum.StrEnum):
    ON_LIST = "on_list"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class ImportedBook:
    book_id: uuid.UUID
    title: str
    entry_id: uuid.UUID
    new_to_catalog: bool


@dataclass(frozen=True, slots=True)
class SkippedBook:
    book_id: uuid.UUID
    title: str
    reason: SkipReason


@dataclass(frozen=True, slots=True)
class ImportResult:
    added: tuple[ImportedBook, ...]
    skipped: tuple[SkippedBook, ...]


@dataclass(frozen=True, slots=True)
class SourceRef:
    source: str
    source_work_id: str
    imported_at: datetime

    @property
    def url(self) -> str:
        return f"https://openlibrary.org/works/{self.source_work_id}"
