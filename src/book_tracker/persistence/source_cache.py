"""Open Library answers kept for 24 hours, outside the catalog (spec 002 FR-017, R5, R8).

Keys follow constitution 1.0.1, Principle III: an author search by normalized name, an
author's works by Open Library author key. Rows hold no user ids. Writing a row first
deletes every expired row.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain.imports import (
    SOURCE_OPEN_LIBRARY,
    AuthorCandidate,
    WorkCandidate,
    WorkList,
)
from book_tracker.persistence import models

TTL = timedelta(hours=24)
AUTHOR_SEARCH = "author_search"
AUTHOR_WORKS = "author_works"


@dataclass(frozen=True, slots=True)
class Cached[T]:
    value: T
    fetched_at: datetime
    expires_at: datetime


# --------------------------------------------------------------------------- (de)serialize


def _author_json(author: AuthorCandidate) -> dict[str, Any]:
    return asdict(author)


def _author(data: dict[str, Any]) -> AuthorCandidate:
    return AuthorCandidate(**data)


def _work_json(work: WorkCandidate) -> dict[str, Any]:
    return {
        "source_id": work.source_id,
        "alias_ids": list(work.alias_ids),
        "title": work.title,
        "first_publish_year": work.first_publish_year,
        "author_names": list(work.author_names),
        "isbn13s": sorted(work.isbn13s),
        "edition_count": work.edition_count,
    }


def _work(data: dict[str, Any]) -> WorkCandidate:
    return WorkCandidate(
        source_id=data["source_id"],
        alias_ids=tuple(data["alias_ids"]),
        title=data["title"],
        first_publish_year=data["first_publish_year"],
        author_names=tuple(data["author_names"]),
        isbn13s=frozenset(data["isbn13s"]),
        edition_count=data["edition_count"],
    )


# --------------------------------------------------------------------------- rows


async def _get(
    db: AsyncSession, kind: str, key: str, now: datetime
) -> models.SourceLookupCache | None:
    row: models.SourceLookupCache | None = await db.scalar(
        select(models.SourceLookupCache)
        .where(
            models.SourceLookupCache.source == SOURCE_OPEN_LIBRARY,
            models.SourceLookupCache.kind == kind,
            models.SourceLookupCache.lookup_key == key,
            models.SourceLookupCache.expires_at > now,
        )
        .execution_options(populate_existing=True)
    )
    return row


async def _put(db: AsyncSession, kind: str, key: str, payload: Any, now: datetime) -> None:
    await db.execute(
        delete(models.SourceLookupCache).where(models.SourceLookupCache.expires_at <= now)
    )
    values = {
        "source": SOURCE_OPEN_LIBRARY,
        "kind": kind,
        "lookup_key": key,
        "payload": payload,
        "fetched_at": now,
        "expires_at": now + TTL,
    }
    statement = insert(models.SourceLookupCache).values(**values)
    await db.execute(
        statement.on_conflict_do_update(
            constraint="source_lookup_cache_pkey",
            set_={k: statement.excluded[k] for k in ("payload", "fetched_at", "expires_at")},
        )
    )


async def get_authors(
    db: AsyncSession, key: str, now: datetime
) -> Cached[list[AuthorCandidate]] | None:
    row = await _get(db, AUTHOR_SEARCH, key, now)
    if row is None:
        return None
    return Cached([_author(a) for a in row.payload], row.fetched_at, row.expires_at)


async def put_authors(
    db: AsyncSession, key: str, authors: list[AuthorCandidate], now: datetime
) -> None:
    await _put(db, AUTHOR_SEARCH, key, [_author_json(a) for a in authors], now)


async def get_works(db: AsyncSession, author_key: str, now: datetime) -> Cached[WorkList] | None:
    row = await _get(db, AUTHOR_WORKS, author_key, now)
    if row is None:
        return None
    data = row.payload
    listing = WorkList(
        author=_author(data["author"]),
        works=tuple(_work(w) for w in data["works"]),
        total=data["total"],
        truncated=data["truncated"],
    )
    return Cached(listing, row.fetched_at, row.expires_at)


async def put_works(db: AsyncSession, author_key: str, listing: WorkList, now: datetime) -> None:
    payload = {
        "author": _author_json(listing.author),
        "works": [_work_json(w) for w in listing.works],
        "total": listing.total,
        "truncated": listing.truncated,
    }
    await _put(db, AUTHOR_WORKS, author_key, payload, now)


async def find_author(db: AsyncSession, author_key: str, now: datetime) -> AuthorCandidate | None:
    """The author as a still-valid cached search described them, if any (research R3)."""
    row = await db.scalar(
        select(models.SourceLookupCache)
        .where(
            models.SourceLookupCache.source == SOURCE_OPEN_LIBRARY,
            models.SourceLookupCache.kind == AUTHOR_SEARCH,
            models.SourceLookupCache.expires_at > now,
            models.SourceLookupCache.payload.contains([{"source_id": author_key}]),
        )
        .limit(1)
    )
    if row is None:
        return None
    for data in row.payload:
        if data["source_id"] == author_key:
            return _author(data)
    return None  # pragma: no cover - the containment test guarantees a match


async def count_rows(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(models.SourceLookupCache)) or 0)
