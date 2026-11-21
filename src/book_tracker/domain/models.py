"""Domain objects returned by services (Constitution Principle VII).

Plain, frozen dataclasses: no SQLAlchemy or Pydantic. Persistence maps ORM rows to these
(``persistence/mappers.py``) and the API maps these to Pydantic schemas
(``schemas/mappers.py``).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from book_tracker.domain.enums import ReadingStatus, Role, SummaryOrigin


@dataclass(frozen=True, slots=True)
class UserRef:
    id: uuid.UUID
    display_name: str


@dataclass(frozen=True, slots=True)
class Account:
    id: uuid.UUID
    display_name: str
    login: str
    role: Role
    is_active: bool
    must_change_password: bool
    password_hash: str
    created_at: datetime

    @property
    def is_admin(self) -> bool:
        return self.role is Role.ADMIN


@dataclass(frozen=True, slots=True)
class Author:
    id: uuid.UUID
    name: str
    sort_name: str
    is_pen_name: bool
    real_name: str | None
    created_by: UserRef
    created_at: datetime
    updated_by: UserRef
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Series:
    id: uuid.UUID
    name: str
    created_by: UserRef
    created_at: datetime
    updated_by: UserRef
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SeriesRef:
    id: uuid.UUID
    name: str


@dataclass(frozen=True, slots=True)
class BookAuthor:
    id: uuid.UUID
    name: str
    real_name: str | None
    position: int


@dataclass(frozen=True, slots=True)
class Summary:
    id: uuid.UUID
    book_id: uuid.UUID
    text: str
    origin: SummaryOrigin
    model: str | None
    source_urls: tuple[str, ...] | None
    is_current: bool
    created_by: UserRef
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Book:
    id: uuid.UUID
    title: str
    authors: tuple[BookAuthor, ...]
    series: SeriesRef | None
    series_number: Decimal | None
    isbn_13: str | None
    current_summary: Summary | None
    created_by: UserRef
    created_at: datetime
    updated_by: UserRef
    updated_at: datetime
    release_date: date | None = None  # spec 007: expected or actual release


@dataclass(frozen=True, slots=True)
class ReadingEntry:
    id: uuid.UUID
    book: Book
    status: ReadingStatus
    finished_on: date | None
    times_read: int
    notes: str | None
    created_at: datetime
    updated_at: datetime
    pre_ordered: bool = False  # spec 007: the owner's own flag


@dataclass(frozen=True, slots=True)
class ReadingEntryPage:
    items: tuple[ReadingEntry, ...]
    page: int
    page_size: int
    total: int
