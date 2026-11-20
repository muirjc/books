"""The source-adapter interface (Constitution Principle IV; spec 002 research R4).

Services see only this protocol and domain objects; HTTP stays inside the adapters.
Failures raise ``SourceUnavailable`` or ``SourceNotFound`` from ``services.errors``.
"""

from __future__ import annotations

from typing import Protocol

from book_tracker.domain.imports import AuthorCandidate, WorkList
from book_tracker.services.errors import SourceNotFound, SourceUnavailable

__all__ = ["BookSource", "SourceNotFound", "SourceUnavailable"]


class BookSource(Protocol):
    async def search_authors(self, name: str) -> list[AuthorCandidate]:
        """Authors matching a name, in the source's order (FR-001, FR-002)."""
        ...

    async def author_works(
        self, author_key: str, author: AuthorCandidate | None = None
    ) -> WorkList:
        """An author's works, de-duplicated, at most 2,000 (FR-003, FR-004, FR-020).

        ``author`` is the candidate the member chose, when known; otherwise the author's
        details come from the works response (research R3).
        """
        ...


class UnavailableSource:
    """Installed under test when no source is given: every call fails (research R14)."""

    async def search_authors(self, name: str) -> list[AuthorCandidate]:
        raise SourceUnavailable()

    async def author_works(
        self, author_key: str, author: AuthorCandidate | None = None
    ) -> WorkList:
        raise SourceUnavailable()
