"""Annotated input types shared by API request models and page forms (Principle VII)."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, overload

from pydantic import AfterValidator, BeforeValidator, Field, StringConstraints, WithJsonSchema

from book_tracker.domain.values import normalize_name, parse_isbn13, parse_series_number

SEARCH_MAX = 200


@overload
def drop_nul(value: str) -> str: ...
@overload
def drop_nul(value: None) -> None: ...
def drop_nul(value: str | None) -> str | None:
    """PostgreSQL text can't hold NUL, so a search drops it before any query (books-7bq)."""
    return None if value is None else value.replace("\x00", "")


def search_text(value: object) -> str:
    """A page's search box text: no NUL, trimmed, at most ``SEARCH_MAX`` characters."""
    return drop_nul(value if isinstance(value, str) else "").strip()[:SEARCH_MAX]


def _type_ahead(value: Any) -> Any:
    return drop_nul(value).strip() if isinstance(value, str) else value


# A type-ahead ``q`` without NUL or edge spaces, so ``min_length`` refuses a blank one.
TypeAheadText = BeforeValidator(_type_ahead)

SERIES_NUMBER_PATTERN = r"^[0-9]{1,3}(\.[0-9]{1,2})?$"


def _series_number(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, int | float | Decimal) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str):
        raise ValueError("Enter a number from 0 to 999.99")
    return parse_series_number(value)


def _isbn(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("Enter the ISBN as text")
    return parse_isbn13(value)


def _normalize(value: Any) -> Any:
    return normalize_name(value) if isinstance(value, str) else value


def _not_future(value: date | None) -> date | None:
    if value is not None and value > date.today():
        raise ValueError("The date finished can't be in the future")
    return value


SeriesNumberIn = Annotated[
    Decimal | None,
    BeforeValidator(_series_number),
    WithJsonSchema(
        {
            "type": ["string", "null"],
            "pattern": SERIES_NUMBER_PATTERN,
            "description": "Decimal as a string, 0–999.99; only with a series",
        }
    ),
]

Isbn13In = Annotated[
    str | None,
    BeforeValidator(_isbn),
    WithJsonSchema(
        {"type": ["string", "null"], "description": "13 digits after removing spaces and hyphens"}
    ),
]

Title = Annotated[str, BeforeValidator(_normalize), StringConstraints(min_length=1, max_length=300)]
Name = Annotated[str, BeforeValidator(_normalize), StringConstraints(min_length=1, max_length=200)]
# The length limit applies to the text only; blank input becomes None first.
OptionalName = Annotated[
    Annotated[str, StringConstraints(max_length=200)] | None,
    BeforeValidator(lambda v: _normalize(v) or None),
]
FinishedOn = Annotated[date | None, AfterValidator(_not_future)]
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _release_date(value: Any) -> date | None:
    """Strictly YYYY-MM-DD (or a date), years 1000–9999: no timestamps or other formats
    (spec 007 R7, PR #23 review)."""
    message = "Enter a date like 2027-03-01"
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and _ISO_DATE.match(value):
        try:
            parsed = date.fromisoformat(value)
        except ValueError:  # a day that doesn't exist, such as 2027-02-30
            raise ValueError(message) from None
    else:
        raise ValueError(message)
    if parsed.year < 1000:
        raise ValueError(message)
    return parsed


# Spec 007: an expected or actual release date.
ReleaseDateIn = Annotated[date | None, BeforeValidator(_release_date)]
Notes = Annotated[str | None, StringConstraints(max_length=10000)]

# Spec 020: the owner's rating. Strict, so "4", 4.5 and true are refused rather than coerced.
Rating = Annotated[int, Field(strict=True, ge=1, le=5)]
RATING_VALUES = ("1", "2", "3", "4", "5")


def _strip(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


# A hand-written summary: 1–5,000 characters after trimming (FR-024).
SummaryText = Annotated[
    str, BeforeValidator(_strip), StringConstraints(min_length=1, max_length=5000)
]
OptionalSummary = Annotated[
    Annotated[str, StringConstraints(max_length=5000)] | None,
    BeforeValidator(lambda v: _strip(v) or None),
]
