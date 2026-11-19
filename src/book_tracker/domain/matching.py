"""Matching imported works to each other and to the catalog (spec 002 research R6).

Stored titles and names go through ``clean`` (NFKC, collapsed whitespace) and ``fit``, so
the database's ``lower(name)`` uniqueness and these comparisons see the same text (FR-022).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from book_tracker.domain.imports import WorkCandidate

TITLE_MAX = 300  # book.title
NAME_MAX = 200  # author.name
_LEADING_ARTICLE = re.compile(r"^(the|a|an)\s+")
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


def clean(value: str) -> str:
    """NFKC with whitespace collapsed: the form stored in the catalog."""
    return " ".join(unicodedata.normalize("NFKC", value).split())


def fit(value: str, limit: int) -> str:
    """``clean`` the value; cut it at a word boundary with "…" if longer than ``limit``."""
    text = clean(value)
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip() + "…"


def normalize_person_name(name: str) -> str:
    return clean(name).casefold()


def normalize_title(title: str) -> str:
    text = _PUNCTUATION.sub(" ", clean(title).casefold())
    text = " ".join(text.split())
    return _LEADING_ARTICLE.sub("", text, count=1)


def _isbn13_check(first12: str) -> str:
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(first12))
    return str((10 - total % 10) % 10)


def isbn10_to_13(raw: str) -> str | None:
    """A valid ISBN-10 as ISBN-13, or ``None``."""
    digits = raw.replace("-", "").replace(" ", "").upper()
    if not re.fullmatch(r"\d{9}[\dX]", digits):
        return None
    total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(digits))
    if total % 11 != 0:
        return None
    first12 = "978" + digits[:9]
    return first12 + _isbn13_check(first12)


def to_isbn13(raw: str) -> str | None:
    """A valid ISBN-13 (as given, or converted from ISBN-10), or ``None``."""
    digits = raw.replace("-", "").replace(" ", "")
    if re.fullmatch(r"\d{13}", digits):
        return digits if _isbn13_check(digits[:12]) == digits[12] else None
    return isbn10_to_13(digits)


def work_key(work: WorkCandidate) -> tuple[str, str]:
    first_author = work.author_names[0] if work.author_names else ""
    return (normalize_title(work.title), normalize_person_name(first_author))


def merge_duplicate_works(works: Iterable[WorkCandidate]) -> list[WorkCandidate]:
    """One entry per (normalized title, normalized first author), in first-seen order.

    The merged entry keeps the id of the work with most editions, every other id as an
    alias, the earliest first published year and the union of ISBNs (AC-12).
    """
    groups: dict[tuple[str, str], list[WorkCandidate]] = {}
    for work in works:
        groups.setdefault(work_key(work), []).append(work)
    merged: list[WorkCandidate] = []
    for group in groups.values():
        lead = max(group, key=lambda w: w.edition_count)
        years = [w.first_publish_year for w in group if w.first_publish_year is not None]
        aliases = [i for w in group for i in w.all_ids if i != lead.source_id]
        merged.append(
            WorkCandidate(
                source_id=lead.source_id,
                alias_ids=tuple(dict.fromkeys(aliases)),
                title=lead.title,
                first_publish_year=min(years) if years else None,
                author_names=lead.author_names,
                isbn13s=frozenset().union(*(w.isbn13s for w in group)),
                edition_count=lead.edition_count,
            )
        )
    return merged
