"""ORM rows → domain objects (Constitution Principle VII). Repositories return only these."""

from __future__ import annotations

from book_tracker.domain import models as domain
from book_tracker.domain.enums import ReadingStatus, Role, SummaryOrigin
from book_tracker.persistence import models as orm


def to_user_ref(row: orm.AppUser) -> domain.UserRef:
    return domain.UserRef(id=row.id, display_name=row.display_name)


def to_account(row: orm.AppUser) -> domain.Account:
    return domain.Account(
        id=row.id,
        display_name=row.display_name,
        login=row.login,
        role=Role(row.role),
        is_active=row.is_active,
        must_change_password=row.must_change_password,
        password_hash=row.password_hash,
        created_at=row.created_at,
    )


def to_author(row: orm.Author) -> domain.Author:
    return domain.Author(
        id=row.id,
        name=row.name,
        sort_name=row.sort_name,
        is_pen_name=row.is_pen_name,
        real_name=row.real_name,
        created_by=to_user_ref(row.created_by_user),
        created_at=row.created_at,
        updated_by=to_user_ref(row.updated_by_user),
        updated_at=row.updated_at,
    )


def to_series(row: orm.Series) -> domain.Series:
    return domain.Series(
        id=row.id,
        name=row.name,
        created_by=to_user_ref(row.created_by_user),
        created_at=row.created_at,
        updated_by=to_user_ref(row.updated_by_user),
        updated_at=row.updated_at,
    )


def to_summary(row: orm.BookSummary) -> domain.Summary:
    return domain.Summary(
        id=row.id,
        book_id=row.book_id,
        text=row.text,
        origin=SummaryOrigin(row.origin),
        model=row.model,
        source_urls=tuple(str(url) for url in row.source_urls) if row.source_urls else None,
        is_current=row.is_current,
        created_by=to_user_ref(row.created_by_user),
        created_at=row.created_at,
    )


def to_book(row: orm.Book) -> domain.Book:
    links = sorted(row.author_links, key=lambda link: link.position)
    return domain.Book(
        id=row.id,
        title=row.title,
        authors=tuple(
            domain.BookAuthor(
                id=link.author.id,
                name=link.author.name,
                real_name=link.author.real_name,
                position=link.position,
            )
            for link in links
        ),
        series=domain.SeriesRef(id=row.series.id, name=row.series.name) if row.series else None,
        series_number=row.series_number,
        isbn_13=row.isbn_13,
        current_summary=to_summary(row.current_summary) if row.current_summary else None,
        created_by=to_user_ref(row.created_by_user),
        created_at=row.created_at,
        updated_by=to_user_ref(row.updated_by_user),
        updated_at=row.updated_at,
        release_date=row.release_date,
    )


def to_reading_entry(row: orm.ReadingEntry) -> domain.ReadingEntry:
    return domain.ReadingEntry(
        id=row.id,
        book=to_book(row.book),
        status=ReadingStatus(row.status),
        finished_on=row.finished_on,
        times_read=row.times_read,
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
        pre_ordered=row.pre_ordered,
    )
