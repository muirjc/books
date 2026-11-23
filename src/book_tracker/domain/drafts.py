"""AI summary drafts (spec 012): what the AI is given, what it returns, and the rules a draft
must pass before it is shown (research R4–R7).

Pure functions and values only; no I/O.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from book_tracker.domain.matching import normalize_person_name, normalize_title

DRAFT_TTL = timedelta(days=30)
WORDS_MIN = 60  # the AI is asked for 100–200; the band allows small misses (AC-12)
WORDS_MAX = 250
COPY_RUN = 12  # consecutive words shared with a source description (AC-13)
SOURCES_MAX = 20
URL_MAX = 2000

# For the web search tool (subdomains are covered); ``is_blocked`` also catches every other
# Amazon storefront after the answer (Principle IV).
BLOCKED_DOMAINS: tuple[str, ...] = (
    "amazon.com",
    "amazon.co.uk",
    "amazon.ca",
    "amazon.com.au",
    "amazon.de",
    "amazon.fr",
    "amazon.in",
    "amazon.co.jp",
    "goodreads.com",
)

DraftStatus = Literal["ok", "not_enough_information"]
Origin = Literal["ai", "ai_edited", "manual"]


@dataclass(frozen=True, slots=True)
class BookFacts:
    """The only book data sent to the AI (Principle IX, research R7)."""

    title: str
    authors: tuple[str, ...]
    series_name: str | None = None
    series_number: Decimal | None = None
    isbn13: str | None = None
    release_year: int | None = None

    @property
    def key(self) -> str:
        return draft_key(self.isbn13, self.title, self.authors)


@dataclass(frozen=True, slots=True)
class BookDescription:
    """Open Library's description of the book and the page it came from (research R3)."""

    work_url: str
    description: str


@dataclass(frozen=True, slots=True)
class GeneratedDraft:
    """What the generator returns, before the checks."""

    status: DraftStatus
    text: str
    source_urls: tuple[str, ...]
    known_urls: frozenset[str]  # every search-result and cited URL in the response
    cited_urls: tuple[str, ...]
    series_name: str | None
    series_number: str | None
    model: str


@dataclass(frozen=True, slots=True)
class StoredDraft:
    """The parts of a cached draft that decide a saved summary's origin."""

    draft_key: str
    text: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CachedDraft:
    """A stored draft (``summary_draft`` row)."""

    id: str
    draft_key: str
    text: str
    source_urls: tuple[str, ...]
    model: str
    series_name: str | None
    series_number: Decimal | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DraftView:
    """A draft as pages and the API show it."""

    id: str
    text: str
    source_urls: tuple[str, ...]
    model: str
    series_name: str | None
    series_number: Decimal | None
    cached: bool
    created_at: datetime
    drafts_left: int


def draft_key(isbn13: str | None, title: str, authors: Iterable[str]) -> str:
    """The cache key: the normalized title and authors, after the ISBN-13 when known.

    The title and authors are part of an ISBN key too, so fixing a book's title or authors
    never brings back a draft written for the old details (AC-17, PR #32 review).
    """
    names = sorted(normalize_person_name(a) for a in authors)
    details = f"{normalize_title(title)}|{'|'.join(names)}"
    return f"isbn:{isbn13}|{details}" if isbn13 else f"ta:{details}"


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def word_count(text: str) -> int:
    return sum(1 for token in text.split() if re.search(r"\w", token))


_WORD = re.compile(r"[\w']+")


def _words(text: str) -> list[str]:
    return _WORD.findall(text.replace("’", "'").casefold())


def copies_source(text: str, description: str | None, run: int = COPY_RUN) -> bool:
    """Whether ``text`` repeats ``run`` or more consecutive words of ``description``."""
    if not description:
        return False
    source = _words(description)
    runs = {tuple(source[i : i + run]) for i in range(len(source) - run + 1)}
    words = _words(text)
    return any(tuple(words[i : i + run]) in runs for i in range(len(words) - run + 1))


def is_blocked(url: str) -> bool:
    """Amazon (any storefront) or Goodreads, including subdomains (AC-11)."""
    try:
        host = (urlsplit(url).hostname or "").casefold()
    except ValueError:
        return False
    labels = host.split(".")
    if host == "goodreads.com" or host.endswith(".goodreads.com"):
        return True
    return "amazon" in labels[:-1]


def keep_sources(
    listed: Sequence[str], known: set[str] | frozenset[str], cited: Sequence[str]
) -> tuple[str, ...]:
    """The URLs to record: those the AI lists that the response really contains, or else
    the cited ones; de-duplicated, at most 20, each at most 2,000 characters (R5)."""
    chosen = [u for u in listed if u in known] or list(cited)
    kept: list[str] = []
    for url in chosen:
        if len(url) <= URL_MAX and url not in kept:
            kept.append(url)
    return tuple(kept[:SOURCES_MAX])


def is_current(draft: StoredDraft | CachedDraft, book_key: str, now: datetime) -> bool:
    """The app's own draft of this book, still within its 30 days."""
    return draft.draft_key == book_key and now - draft.created_at <= DRAFT_TTL


def origin_for(
    draft: StoredDraft | CachedDraft | None, book_key: str, saved_text: str, now: datetime
) -> Origin:
    """``ai`` or ``ai_edited`` only for the app's own, current draft of this book (R6)."""
    if draft is None or not is_current(draft, book_key, now):
        return "manual"
    return "ai" if normalize_text(saved_text) == normalize_text(draft.text) else "ai_edited"
