"""Domain objects → API schemas (Constitution Principle VII)."""

from __future__ import annotations

from book_tracker.domain import models as domain
from book_tracker.domain.values import format_series_number
from book_tracker.schemas import catalog as c
from book_tracker.schemas import readings as r
from book_tracker.schemas.accounts import Account
from book_tracker.schemas.auth import CurrentUser


def to_current_user(account: domain.Account, csrf_token: str) -> CurrentUser:
    return CurrentUser(
        id=account.id,
        display_name=account.display_name,
        login=account.login,
        role=account.role,
        must_change_password=account.must_change_password,
        csrf_token=csrf_token,
    )


def user_ref_out(ref: domain.UserRef) -> c.UserRef:
    return c.UserRef(id=ref.id, display_name=ref.display_name)


def summary_out(summary: domain.Summary) -> c.Summary:
    return c.Summary(
        id=summary.id,
        book_id=summary.book_id,
        text=summary.text,
        origin=summary.origin,
        model=summary.model,
        source_urls=list(summary.source_urls) if summary.source_urls else None,
        is_current=summary.is_current,
        created_by=user_ref_out(summary.created_by),
        created_at=summary.created_at,
    )


def author_out(author: domain.Author) -> c.Author:
    return c.Author(
        id=author.id,
        name=author.name,
        sort_name=author.sort_name,
        is_pen_name=author.is_pen_name,
        real_name=author.real_name,
        created_by=user_ref_out(author.created_by),
        created_at=author.created_at,
        updated_by=user_ref_out(author.updated_by),
        updated_at=author.updated_at,
    )


def series_out(series: domain.Series) -> c.Series:
    return c.Series(
        id=series.id,
        name=series.name,
        created_by=user_ref_out(series.created_by),
        created_at=series.created_at,
        updated_by=user_ref_out(series.updated_by),
        updated_at=series.updated_at,
    )


def book_out(book: domain.Book) -> c.Book:
    return c.Book(
        id=book.id,
        title=book.title,
        authors=[
            c.BookAuthorRef(id=a.id, name=a.name, real_name=a.real_name, position=a.position)
            for a in book.authors
        ],
        series=c.SeriesRef(id=book.series.id, name=book.series.name) if book.series else None,
        series_number=(
            format_series_number(book.series_number) if book.series_number is not None else None
        ),
        isbn_13=book.isbn_13,
        current_summary=summary_out(book.current_summary) if book.current_summary else None,
        created_by=user_ref_out(book.created_by),
        created_at=book.created_at,
        updated_by=user_ref_out(book.updated_by),
        updated_at=book.updated_at,
    )


def reading_entry_out(entry: domain.ReadingEntry) -> r.ReadingEntry:
    return r.ReadingEntry(
        id=entry.id,
        book=book_out(entry.book),
        status=entry.status,
        finished_on=entry.finished_on,
        times_read=entry.times_read,
        notes=entry.notes,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def reading_entry_page_out(page: domain.ReadingEntryPage) -> r.ReadingEntryPage:
    return r.ReadingEntryPage(
        items=[reading_entry_out(e) for e in page.items],
        page=page.page,
        page_size=page.page_size,
        total=page.total,
    )


def account_out(account: domain.Account) -> Account:
    """Never includes the password hash."""
    return Account(
        id=account.id,
        display_name=account.display_name,
        login=account.login,
        role=account.role,
        is_active=account.is_active,
        must_change_password=account.must_change_password,
        created_at=account.created_at,
    )


def my_series_view_out(
    series: domain.Series, entries: tuple[domain.ReadingEntry, ...]
) -> r.MySeriesView:
    return r.MySeriesView(
        series=c.SeriesRef(id=series.id, name=series.name),
        entries=[reading_entry_out(e) for e in entries],
    )
