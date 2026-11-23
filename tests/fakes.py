"""Test doubles for spec 002 (research R14): a book source that never touches the network."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from book_tracker.domain.drafts import BookDescription
from book_tracker.domain.imports import AuthorCandidate, WorkCandidate, WorkList
from book_tracker.services.errors import SourceNotFound


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
