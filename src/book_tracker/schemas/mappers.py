"""Domain objects → API schemas (Constitution Principle VII)."""

from __future__ import annotations

import uuid

from book_tracker.domain import imports as imports_domain
from book_tracker.domain import models as domain
from book_tracker.domain.drafts import DraftView
from book_tracker.domain.values import format_series_number
from book_tracker.schemas import catalog as c
from book_tracker.schemas import imports as i
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
        release_date=book.release_date,
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
        pre_ordered=entry.pre_ordered,
        rating=entry.rating,
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


# --------------------------------------------------------------------------- spec 002 imports


def author_candidate_out(author: imports_domain.AuthorCandidate) -> i.AuthorCandidate:
    return i.AuthorCandidate(
        author_key=author.source_id,
        name=author.name,
        birth_date=author.birth_date,
        death_date=author.death_date,
        top_work=author.top_work,
        work_count=author.work_count,
    )


def works_view_out(view: imports_domain.WorksView) -> i.WorkList:
    return i.WorkList(
        author=author_candidate_out(view.author),
        works=[
            i.WorkCandidate(
                work_key=w.work.source_id,
                title=w.work.title,
                first_publish_year=w.work.first_publish_year,
                author_names=list(w.work.author_names),
                state=w.state,
                book_id=w.book_id,
            )
            for w in view.works
        ],
        total=view.total,
        truncated=view.truncated,
        fetched_at=view.fetched_at,
    )


def import_result_out(result: imports_domain.ImportResult) -> i.ImportResult:
    return i.ImportResult(
        added=[
            i.ImportedBook(
                book_id=b.book_id, title=b.title, entry_id=b.entry_id,
                new_to_catalog=b.new_to_catalog,
            )
            for b in result.added
        ],
        skipped=[
            i.SkippedBook(book_id=s.book_id, title=s.title, reason=s.reason)
            for s in result.skipped
        ],
    )  # fmt: skip


def story_out(story: domain.Story) -> c.Story:
    return c.Story(
        id=story.id,
        title=story.title,
        authors=[
            c.BookAuthorRef(id=a.id, name=a.name, real_name=a.real_name, position=a.position)
            for a in story.authors
        ],
        series=c.SeriesRef(id=story.series.id, name=story.series.name) if story.series else None,
        series_number=(
            format_series_number(story.series_number) if story.series_number is not None else None
        ),
        books=[c.BookRef(id=ref.id, title=ref.title) for ref in story.books],
        created_by=user_ref_out(story.created_by),
        created_at=story.created_at,
        updated_by=user_ref_out(story.updated_by),
        updated_at=story.updated_at,
    )


def summary_draft_out(view: DraftView) -> c.SummaryDraft:
    suggestion = (
        c.SeriesSuggestionOut(
            name=view.series_name,
            number=format_series_number(view.series_number)
            if view.series_number is not None
            else None,
        )
        if view.series_name
        else None
    )
    return c.SummaryDraft(
        id=uuid.UUID(view.id),
        text=view.text,
        source_urls=list(view.source_urls),
        model=view.model,
        series_suggestion=suggestion,
        cached=view.cached,
        created_at=view.created_at,
        drafts_left_today=view.drafts_left,
    )
