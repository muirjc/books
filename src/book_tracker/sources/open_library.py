"""Open Library adapter (spec 002; research R2, R3, R6, R9).

Uses the official JSON API: ``/search/authors.json`` and ``/search.json?author_key=``.
Requests carry only the author name or Open Library keys and a User-Agent naming the app
(FR-015, FR-018). Responses are parsed with private Pydantic models and returned as domain
objects; raw dicts never leave this module (Principle VII).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from book_tracker.domain.imports import (
    MAX_WORKS_LISTED,
    AuthorCandidate,
    WorkCandidate,
    WorkList,
)
from book_tracker.domain.matching import (
    NAME_MAX,
    TITLE_MAX,
    fit,
    merge_duplicate_works,
    normalize_person_name,
    to_isbn13,
)
from book_tracker.services.errors import SourceNotFound, SourceUnavailable
from book_tracker.sources.rate_limit import RateLimiter

logger = logging.getLogger("book_tracker.sources.open_library")

AUTHOR_SEARCH_LIMIT = 10
WORKS_PAGE_SIZE = 1000
MAX_PAGES = MAX_WORKS_LISTED // WORKS_PAGE_SIZE
WORK_FIELDS = (
    "key",
    "title",
    "first_publish_year",
    "author_name",
    "author_key",
    "isbn",
    "edition_count",
)


def user_agent() -> str:
    """``FamilyBookTracker/<version>``: the app only, no contact address (Principle IX)."""
    try:
        app_version = version("book-tracker")
    except PackageNotFoundError:  # pragma: no cover - always installed via uv
        app_version = "0"
    return f"FamilyBookTracker/{app_version}"


def make_client(
    base_url: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        headers={"User-Agent": user_agent(), "Accept": "application/json"},
        timeout=httpx.Timeout(10.0, connect=5.0),
        follow_redirects=False,
        transport=transport,
    )


# --------------------------------------------------------------------------- responses


class _AuthorDoc(BaseModel):
    key: str
    name: str
    birth_date: str | None = None
    death_date: str | None = None
    top_work: str | None = None
    work_count: int = 0


class _AuthorSearch(BaseModel):
    docs: list[dict[str, Any]] = []


class _WorkDoc(BaseModel):
    key: str
    title: str
    first_publish_year: int | None = None
    author_name: list[str]
    author_key: list[str] = []
    isbn: list[str] = []
    edition_count: int = 0


class _WorkSearch(BaseModel):
    numFound: int = 0  # noqa: N815 - Open Library's field name
    docs: list[dict[str, Any]] = []


_AUTHOR_ID = re.compile(r"OL[0-9]+A")
_WORK_ID = re.compile(r"OL[0-9]+W")


def _short_key(key: str) -> str:
    return key.rsplit("/", 1)[-1]


def _author(doc: _AuthorDoc) -> AuthorCandidate | None:
    source_id = _short_key(doc.key)
    if not _AUTHOR_ID.fullmatch(source_id):
        return None  # the pages and the API only accept OL…A ids
    return AuthorCandidate(
        source_id=source_id,
        name=fit(doc.name, NAME_MAX),
        birth_date=doc.birth_date,
        death_date=doc.death_date,
        top_work=fit(doc.top_work, TITLE_MAX) if doc.top_work else None,
        work_count=doc.work_count,
    )


def _work(doc: _WorkDoc) -> WorkCandidate | None:
    title = fit(doc.title, TITLE_MAX)
    names: list[str] = []
    seen: set[str] = set()
    for raw in doc.author_name:
        name = fit(raw, NAME_MAX)
        key = normalize_person_name(name)
        if name and key not in seen:  # an author listed twice is added once (FR-021)
            seen.add(key)
            names.append(name)
    if not title or not names:
        return None
    source_id = _short_key(doc.key)
    if not _WORK_ID.fullmatch(source_id):
        return None  # book_source_ref only holds OL…W ids (review finding 4)
    isbns = {i for i in (to_isbn13(raw) for raw in doc.isbn) if i}
    return WorkCandidate(
        source_id=source_id,
        alias_ids=(),
        title=title,
        first_publish_year=doc.first_publish_year,
        author_names=tuple(names),
        isbn13s=frozenset(isbns),
        edition_count=doc.edition_count,
    )


# --------------------------------------------------------------------------- adapter


class OpenLibrarySource:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        timeout_seconds: float = 10.0,
        limiter: RateLimiter | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._budget = timeout_seconds
        self._limiter = limiter or RateLimiter(clock=clock)
        self._clock = clock

    async def _get(self, kind: str, path: str, params: dict[str, Any], deadline: float) -> Any:
        await self._limiter.acquire(deadline)
        started = self._clock()
        remaining = deadline - started
        if remaining <= 0:
            raise SourceUnavailable()
        try:
            async with asyncio.timeout(remaining):
                response = await self._client.get(path, params=params)
        except (TimeoutError, httpx.HTTPError) as exc:
            logger.info("open library %s failed: %s", kind, type(exc).__name__)
            raise SourceUnavailable() from None
        logger.info(
            "open library %s: %s in %.2fs", kind, response.status_code, self._clock() - started
        )
        if response.status_code != 200:
            raise SourceUnavailable()
        try:
            return response.json()
        except ValueError:
            raise SourceUnavailable() from None

    async def search_authors(self, name: str) -> list[AuthorCandidate]:
        deadline = self._clock() + self._budget
        data = await self._get(
            "author_search",
            "/search/authors.json",
            {"q": name, "limit": AUTHOR_SEARCH_LIMIT},
            deadline,
        )
        try:
            docs = _AuthorSearch.model_validate(data).docs
        except ValidationError:
            raise SourceUnavailable() from None
        authors: list[AuthorCandidate] = []
        for raw in docs:
            try:
                candidate = _author(_AuthorDoc.model_validate(raw))
            except ValidationError:
                candidate = None
            if candidate is None:
                logger.info("open library author_search: dropped a malformed author")
            else:
                authors.append(candidate)
        return authors

    async def author_works(
        self, author_key: str, author: AuthorCandidate | None = None
    ) -> WorkList:
        deadline = self._clock() + self._budget  # one budget for every page (research R9)
        works: list[WorkCandidate] = []
        total = 0
        header_name: str | None = None
        for page in range(1, MAX_PAGES + 1):
            params = {
                "author_key": author_key,
                "fields": ",".join(WORK_FIELDS),
                "limit": WORKS_PAGE_SIZE,
                "page": page,
            }
            data = await self._get("author_works", "/search.json", params, deadline)
            try:
                result = _WorkSearch.model_validate(data)
            except ValidationError:
                raise SourceUnavailable() from None
            total = result.numFound
            dropped = 0
            for raw in result.docs:
                try:
                    doc = _WorkDoc.model_validate(raw)
                except ValidationError:
                    dropped += 1
                    continue
                if header_name is None and author_key in doc.author_key:
                    index = doc.author_key.index(author_key)
                    if index < len(doc.author_name):
                        header_name = doc.author_name[index]
                work = _work(doc)
                if work is None:
                    dropped += 1
                else:
                    works.append(work)
            if dropped:
                logger.info("open library author_works: dropped %d malformed works", dropped)
            if page * WORKS_PAGE_SIZE >= total or not result.docs:
                break
        if total == 0:
            raise SourceNotFound()
        if author is None:
            author = AuthorCandidate(
                source_id=author_key,
                name=fit(header_name or author_key, NAME_MAX),
                birth_date=None,
                death_date=None,
                top_work=None,
                work_count=total,
            )
        merged = merge_duplicate_works(works)[:MAX_WORKS_LISTED]
        return WorkList(
            author=author, works=tuple(merged), total=total, truncated=total > MAX_WORKS_LISTED
        )
