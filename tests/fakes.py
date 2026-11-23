"""Test doubles for spec 002 (research R14): a book source that never touches the network."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field

from book_tracker.domain.drafts import BookDescription, BookFacts, GeneratedDraft
from book_tracker.domain.imports import AuthorCandidate, WorkCandidate, WorkList
from book_tracker.services.errors import AiNotConfigured, SourceNotFound


@dataclass
class FakeBookSource:
    """Serves configured answers; ``error`` makes every call raise it."""

    authors: dict[str, list[AuthorCandidate]] = field(default_factory=dict)
    works: dict[str, WorkList] = field(default_factory=dict)
    error: Exception | None = None
    calls: list[tuple[str, str]] = field(default_factory=list)
    descriptions: dict[str, BookDescription] = field(default_factory=dict)  # by title

    async def search_authors(self, name: str) -> list[AuthorCandidate]:
        self.calls.append(("search_authors", name))
        if self.error is not None:
            raise self.error
        return list(self.authors.get(name.casefold(), []))

    async def author_works(
        self, author_key: str, author: AuthorCandidate | None = None
    ) -> WorkList:
        self.calls.append(("author_works", author_key))
        if self.error is not None:
            raise self.error
        if author_key not in self.works:
            raise SourceNotFound()
        listing = self.works[author_key]
        if author is not None:
            listing = WorkList(author, listing.works, listing.total, listing.truncated)
        return listing

    async def describe_book(
        self, title: str, authors: Sequence[str], isbn13: str | None
    ) -> BookDescription | None:
        self.calls.append(("describe_book", title))
        if self.error is not None:
            raise self.error
        return self.descriptions.get(title.casefold())


def author(key: str = "OL1A", name: str = "Ann Author", works: int = 3) -> AuthorCandidate:
    return AuthorCandidate(key, name, "1950", None, "First Book", works)


def work(
    n: int,
    title: str | None = None,
    authors: tuple[str, ...] = ("Ann Author",),
    *,
    year: int | None = 2000,
    isbns: frozenset[str] = frozenset(),
    aliases: tuple[str, ...] = (),
) -> WorkCandidate:
    return WorkCandidate(
        source_id=f"OL{n}W",
        alias_ids=aliases,
        title=title or f"Book {n}",
        first_publish_year=year,
        author_names=authors,
        isbn13s=isbns,
        edition_count=1,
    )


def listing(key: str, works: list[WorkCandidate], *, name: str = "Ann Author",
            total: int | None = None) -> WorkList:  # fmt: skip
    count = total if total is not None else len(works)
    return WorkList(author(key, name, count), tuple(works), count, count > 2000)


# --------------------------------------------------------------------------- spec 012

WIKI = "https://en.wikipedia.org/wiki/Example_(novel)"
DRAFT_TEXT = (
    "In a city that never quite believes in magic, a tired detective with an unusual gift "
    "takes on a case nobody else will touch. A string of strange deaths has the police "
    "baffled, and the only lead points toward a world most people would rather ignore. "
    "With rent overdue, an old enemy watching and a client who is hiding something, the "
    "detective must decide how far to trust the people who hired him. The story opens a "
    "long-running series with humour, warmth and a steady build of tension, and it sets up "
    "the friendships and rivalries that carry through the later books."
)


def good_draft(**changes: object) -> GeneratedDraft:
    values: dict[str, object] = {
        "status": "ok",
        "text": DRAFT_TEXT,
        "source_urls": (WIKI,),
        "known_urls": frozenset({WIKI}),
        "cited_urls": (WIKI,),
        "series_name": None,
        "series_number": None,
        "model": "claude-opus-5-5",
    }
    values.update(changes)
    return GeneratedDraft(**values)  # type: ignore[arg-type]  # test values are the right types


@dataclass
class FakeSummaryGenerator:
    """Answers with scripted drafts or errors, in order, then ``good_draft()``. ``delay``
    makes every call wait first; ``configured`` False behaves like a server with no key."""

    results: list[GeneratedDraft | Exception] = field(default_factory=list)
    calls: list[tuple[BookFacts, BookDescription | None]] = field(default_factory=list)
    delay: float = 0.0
    configured: bool = True

    async def draft(self, facts: BookFacts, description: BookDescription | None) -> GeneratedDraft:
        if not self.configured:
            raise AiNotConfigured()
        self.calls.append((facts, description))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.results:
            result = self.results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        return good_draft()
