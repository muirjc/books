"""Value rules: ISBN-13, number in series, names (FR-011, FR-013, FR-015)."""

from __future__ import annotations

import difflib
import re
import unicodedata
import uuid
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

SERIES_NUMBER_MAX = Decimal("999.99")
SORT_NAME_MAX = 200  # author.sort_name
PEN_NAME_FIRST = "Mark the author as a pen name first"  # FR-014
_SERIES_NUMBER = re.compile(r"^\d{1,3}(\.\d{1,2})?$")
_LEADING_THE = re.compile(r"^the\s+")
_NOT_LETTER_OR_DIGIT = re.compile(r"[\W_]+")
SIMILAR_CUTOFF = 0.75  # spec 005 R3: typos score 0.86+, unrelated names 0.55 or less
SIMILAR_LIMIT = 3


def normalize_name(value: str) -> str:
    """Trim and collapse inner whitespace (data-model.md)."""
    return " ".join(value.split())


def default_sort_name(name: str) -> str:
    """ "J.K. Rowling" → "Rowling, J.K."; single words are unchanged."""
    parts = normalize_name(name).split(" ")
    if len(parts) < 2:
        return parts[0] if parts else ""
    sort = f"{parts[-1]}, {' '.join(parts[:-1])}"
    return sort[:SORT_NAME_MAX].rstrip()  # one longer than the name; author.sort_name is 200


def parse_isbn13(raw: str) -> str:
    """Return the 13 digits of a valid ISBN-13, ignoring spaces and hyphens."""
    digits = re.sub(r"[\s-]", "", raw)
    if not re.fullmatch(r"\d{13}", digits):
        raise ValueError("An ISBN must have 13 digits")
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12]))
    check = (10 - total % 10) % 10
    if check != int(digits[12]):
        raise ValueError("This ISBN's check digit is wrong")
    return digits


def parse_series_number(raw: str) -> Decimal:
    """A number in series from 0 to 999.99 with at most two decimal places."""
    text = raw.strip()
    if not _SERIES_NUMBER.match(text):
        raise ValueError("Enter a number from 0 to 999.99, with up to two decimal places")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:  # pragma: no cover - the pattern already guards this
        raise ValueError("Enter a number from 0 to 999.99") from exc
    if value > SERIES_NUMBER_MAX:  # pragma: no cover - three integer digits cap at 999
        raise ValueError("Enter a number from 0 to 999.99")
    return value


def format_series_number(value: Decimal) -> str:
    """Decimal → shortest text: 2.50 → "2.5", 3.00 → "3"."""
    text = f"{value.quantize(Decimal('0.01')):f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def loose_name_key(name: str) -> str:
    """A name reduced for "did you mean" matching (spec 005 R3): NFKC, lower case, a
    leading "the " dropped, then only letters and digits ("The Dresden Files" ->
    "dresdenfiles", "J.D. Robb" -> "jdrobb")."""
    text = unicodedata.normalize("NFKC", normalize_name(name)).lower()
    return _NOT_LETTER_OR_DIGIT.sub("", _LEADING_THE.sub("", text))


def similar_names(
    typed: str,
    candidates: Iterable[tuple[uuid.UUID, str, tuple[str, ...]]],
    *,
    limit: int = SIMILAR_LIMIT,
    cutoff: float = SIMILAR_CUTOFF,
) -> list[tuple[uuid.UUID, str]]:
    """Catalog records whose names look like ``typed``, best first (ties by label).

    Each candidate is (id, label, names to compare), e.g. an author's name and real name.
    """
    key = loose_name_key(typed)
    if not key:
        return []
    scored: list[tuple[float, str, uuid.UUID]] = []
    for record_id, label, names in candidates:
        score = max(
            (difflib.SequenceMatcher(None, key, loose_name_key(n)).ratio() for n in names if n),
            default=0.0,
        )
        if score >= cutoff:
            scored.append((score, label, record_id))
    scored.sort(key=lambda s: (-s[0], s[1].lower()))
    return [(record_id, label) for _, label, record_id in scored[:limit]]
