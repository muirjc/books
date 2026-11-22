"""Import an author's books from Open Library (spec 002; research R5-R8, R10).

Coverage-critical (plan.md): this module decides whose list receives imported books. The
member is always the ``user_id`` the caller took from the session; nothing here accepts a
user id from request data (Principle I). Nothing is written to the catalog before
``confirm_import`` (FR-007).
"""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain.enums import ReadingStatus
from book_tracker.domain.imports import (
    MAX_WORKS_PER_IMPORT,
    AuthorCandidate,
    ImportedBook,
    ImportResult,
    SkippedBook,
    SkipReason,
    SourceRef,
    WorkCandidate,
    WorkList,
    WorkListing,
    WorkState,
    WorksView,
)
from book_tracker.domain.matching import clean, normalize_person_name, normalize_title
from book_tracker.persistence import imports as store
from book_tracker.persistence import source_cache
from book_tracker.persistence.readings import ReadingEntryRepository
from book_tracker.services import catalog as catalog_service
from book_tracker.services.errors import ConflictError, SourceUnavailable, ValidationFailed
from book_tracker.services.readings import apply_status_change
from book_tracker.sources.base import BookSource

IMPORT_LOCK = text("SELECT pg_advisory_xact_lock(hashtext('book_tracker.import'))")
REFRESH_BEFORE = timedelta(hours=1)  # a list is never shown with less left (research R8)
TOO_MANY = f"You can add up to {MAX_WORKS_PER_IMPORT} books at a time"
NOTHING_TICKED = "Tick at least one book"
NAME_REQUIRED = "Enter an author's name"
NOT_IN_LIST = "Some books aren't in this author's list"
SEARCH_MAX = 200  # characters, after cleaning (contracts: SearchText)
CACHE_KEY_MAX = 300  # source_lookup_cache.lookup_key
EXPIRED = "These results are more than a day old. Reload the list and confirm again."


# --------------------------------------------------------------------------- searching


async def search_authors(
    db: AsyncSession, source: BookSource, name: str, now: datetime
) -> list[AuthorCandidate]:
    """Authors matching ``name`` (FR-001, FR-002); reused for 24 hours (FR-017)."""
    query = clean(name)
    key = normalize_person_name(query)
    if not query or len(query) > SEARCH_MAX or len(key) > CACHE_KEY_MAX:
        raise ValidationFailed.single("q", NAME_REQUIRED)  # checked after NFKC (finding 5)
    cached = await source_cache.get_authors(db, key, now)
    if cached is not None:
        return cached.value
    authors = await source.search_authors(query)
    await source_cache.put_authors(db, key, authors, now)
    return authors


async def _catalog_matches(
    db: AsyncSession, works: Sequence[WorkCandidate]
) -> dict[str, uuid.UUID]:
    """Work id → catalog book, by source id or alias, ISBN, or title + first author (R6)."""
    found: dict[str, uuid.UUID] = {}
    by_ref = await store.find_books_by_source_ids(db, {i for w in works for i in w.all_ids})
    by_isbn = await store.find_books_by_isbns(db, {i for w in works for i in w.isbn13s})
    keys = await store.name_keys(db, {w.author_names[0] for w in works})
    first_authors = set(keys.values())
    by_title: dict[tuple[str, str], uuid.UUID] = {}
    for book_id, title, author_key in await store.books_by_first_author_names(db, first_authors):
        by_title.setdefault((normalize_title(title), author_key), book_id)
    for work in works:
        match = next((by_ref[i] for i in work.all_ids if i in by_ref), None)
        if match is None:
            match = next((by_isbn[i] for i in sorted(work.isbn13s) if i in by_isbn), None)
        if match is None:
            match = by_title.get((normalize_title(work.title), keys[work.author_names[0]]))
        if match is not None:
            found[work.source_id] = match
    return found


def _sorted(listings: Iterable[WorkListing], sort: str) -> list[WorkListing]:
    if sort == "year":
        return sorted(
            listings,
            key=lambda w: (
                w.work.first_publish_year is None,
                w.work.first_publish_year or 0,
                normalize_title(w.work.title),
            ),
        )
    return sorted(listings, key=lambda w: (normalize_title(w.work.title), w.work.source_id))


async def list_works(
    db: AsyncSession,
    source: BookSource,
    user_id: uuid.UUID,
    author_key: str,
    now: datetime,
    *,
    sort: str = "title",
    q: str | None = None,
) -> WorksView:
    """The author's works with their state for this member (FR-003 to FR-006, FR-020)."""
    cached = await source_cache.get_works(db, author_key, now)
    if cached is not None and cached.expires_at - now >= REFRESH_BEFORE:
        return await _works_view(db, user_id, cached.value, cached.fetched_at, sort=sort, q=q)
    author = await source_cache.find_author(db, author_key, now)
    try:
        listing = await source.author_works(author_key, author)
    except SourceUnavailable:
        if cached is None:
            raise
        # Still valid for under an hour, so show it, saying so (research R8).
        view = await _works_view(db, user_id, cached.value, cached.fetched_at, sort=sort, q=q)
        return dataclasses.replace(view, refresh_failed=True)
    await source_cache.put_works(db, author_key, listing, now)
    fetched_at = now
    return await _works_view(db, user_id, listing, fetched_at, sort=sort, q=q)


async def cached_works(
    db: AsyncSession,
    user_id: uuid.UUID,
    author_key: str,
    now: datetime,
    *,
    sort: str = "title",
    q: str | None = None,
) -> WorksView | None:
    """Like ``list_works`` from the cache only, or None once it has expired.

    For redisplaying after a refused confirm: that runs under the import lock, so it must
    not wait on Open Library (review finding 1).
    """
    cached = await source_cache.get_works(db, author_key, now)
    if cached is None:
        return None
    return await _works_view(db, user_id, cached.value, cached.fetched_at, sort=sort, q=q)


async def _works_view(
    db: AsyncSession,
    user_id: uuid.UUID,
    listing: WorkList,
    fetched_at: datetime,
    *,
    sort: str,
    q: str | None,
) -> WorksView:
    matches = await _catalog_matches(db, listing.works)
    on_list = await ReadingEntryRepository(db, user_id).book_ids_on_list(set(matches.values()))
    rows: list[WorkListing] = []
    for work in listing.works:
        book_id = matches.get(work.source_id)
        if book_id is None:
            state = WorkState.NEW
        elif book_id in on_list:
            state = WorkState.ON_MY_LIST
        else:
            state = WorkState.IN_CATALOG
        rows.append(WorkListing(work, state, book_id))
    on_my_list = frozenset(r.work.source_id for r in rows if r.state is WorkState.ON_MY_LIST)
    if q:
        needle = clean(q).casefold()
        rows = [r for r in rows if needle in r.work.title.casefold()]
    return WorksView(
        author=listing.author,
        works=tuple(_sorted(rows, sort)),
        total=listing.total,
        truncated=listing.truncated,
        fetched_at=fetched_at,
        lead_ids=_lead_ids(listing.works),
        on_my_list=on_my_list,
    )


def _lead_ids(works: Iterable[WorkCandidate]) -> dict[str, str]:
    """Any id of a listed work, merged ones included, → that work's own id (research R6)."""
    return {i: w.source_id for w in works for i in w.all_ids}


# --------------------------------------------------------------------------- confirming


def _constraint(exc: IntegrityError) -> str | None:
    diag = getattr(exc.orig, "diag", None)
    name = getattr(diag, "constraint_name", None)
    return str(name) if name else None


async def _add_new_work(
    db: AsyncSession,
    actor_id: uuid.UUID,
    work: WorkCandidate,
    author_ids: list[uuid.UUID],
    now: datetime,
) -> tuple[uuid.UUID, bool]:
    """Create the book and its source link in a savepoint: (book id, created).

    If another session already linked this Open Library work, reuse that book. The advisory
    lock normally prevents this; the unique constraint is the database's guarantee (R7).
    """
    try:
        async with db.begin_nested():
            book_id = await store.create_imported_book(
                db, title=work.title, author_ids=author_ids, actor_id=actor_id
            )
            await store.insert_source_ref(
                db, book_id=book_id, work_id=work.source_id, actor_id=actor_id, now=now
            )
            return book_id, True
    except IntegrityError as exc:
        if _constraint(exc) != "book_source_ref_source_work_key":
            raise
        existing = await store.find_books_by_source_ids(db, [work.source_id])
        return existing[work.source_id], False


async def _author_ids(
    db: AsyncSession, actor_id: uuid.UUID, works: Sequence[WorkCandidate]
) -> dict[str, uuid.UUID]:
    """Author name (as listed) → author id for every author of these works; missing ones
    are created. Names are matched by the database's key (books-0tw.2)."""
    keys = await store.name_keys(db, {name for work in works for name in work.author_names})
    names: dict[str, str] = {}
    for work in works:
        for name in work.author_names:
            names.setdefault(keys[name], name)
    ids = await store.find_authors_by_names(db, names.keys())
    for key, name in names.items():
        if key in ids:
            continue
        try:
            ids[key] = (await catalog_service.create_author(db, actor_id, name=name)).id
        except ConflictError as exc:  # pragma: no cover - only if created since the look-up
            if exc.code != "author_exists" or exc.existing_id is None:
                raise
            ids[key] = exc.existing_id
    return {name: ids[key] for name, key in keys.items()}


async def confirm_import(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    author_key: str,
    work_keys: Sequence[str],
    status: ReadingStatus,
    now: datetime,
) -> ImportResult:
    """Add the selected works to this member's list, creating catalog books as needed."""
    keys = list(dict.fromkeys(work_keys))
    if not keys:
        raise ValidationFailed.single("work_keys", NOTHING_TICKED)
    if len(keys) > MAX_WORKS_PER_IMPORT:
        raise ValidationFailed.single("work_keys", TOO_MANY)

    await db.execute(IMPORT_LOCK)  # one confirm at a time (research R7)
    cached = await source_cache.get_works(db, author_key, now)
    if cached is None:
        raise ConflictError("results_expired", EXPIRED)
    by_id = {i: w for w in cached.value.works for i in w.all_ids}  # merged ids too
    if any(k not in by_id for k in keys):
        raise ValidationFailed.single("work_keys", NOT_IN_LIST)
    selected = list({by_id[k].source_id: by_id[k] for k in keys}.values())

    matches = await _catalog_matches(db, selected)  # afresh, inside the lock
    new_works = [w for w in selected if w.source_id not in matches]
    authors = await _author_ids(db, user_id, new_works)
    targets: list[tuple[WorkCandidate, uuid.UUID, bool]] = []
    for work in selected:
        if work.source_id in matches:
            targets.append((work, matches[work.source_id], False))
            continue
        author_ids = list(dict.fromkeys(authors[n] for n in work.author_names))
        book_id, created = await _add_new_work(db, user_id, work, author_ids, now)
        targets.append((work, book_id, created))

    repo = ReadingEntryRepository(db, user_id)
    on_list = await repo.book_ids_on_list({book_id for _, book_id, _ in targets})
    times_read = apply_status_change(None, status, 0, None)
    added: list[ImportedBook] = []
    skipped: list[SkippedBook] = []
    seen: set[uuid.UUID] = set()
    for work, book_id, created in targets:
        if book_id in on_list:
            skipped.append(SkippedBook(book_id, work.title, SkipReason.ON_LIST))
            continue
        if book_id in seen:
            skipped.append(SkippedBook(book_id, work.title, SkipReason.DUPLICATE))
            continue
        seen.add(book_id)
        try:
            async with db.begin_nested():
                entry = await repo.add(
                    book_id=book_id, status=status, finished_on=None,
                    times_read=times_read, notes=None,
                )  # fmt: skip
        except IntegrityError as exc:  # pragma: no cover - added from another page meanwhile
            if _constraint(exc) != "reading_entry_user_book_key":
                raise
            skipped.append(SkippedBook(book_id, work.title, SkipReason.ON_LIST))
            continue
        added.append(ImportedBook(book_id, work.title, entry.id, created))
    return ImportResult(added=tuple(added), skipped=tuple(skipped))


async def source_ref(db: AsyncSession, book_id: uuid.UUID) -> SourceRef | None:
    """Where a catalog book was imported from, for its page (FR-009)."""
    return await store.source_ref_for_book(db, book_id)
