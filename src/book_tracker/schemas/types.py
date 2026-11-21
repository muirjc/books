"""Annotated input types shared by API request models and page forms (Principle VII)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from pydantic import AfterValidator, BeforeValidator, StringConstraints, WithJsonSchema

from book_tracker.domain.values import normalize_name, parse_isbn13, parse_series_number

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
# Spec 007: an expected or actual release date; any real calendar date.
ReleaseDateIn = date | None
Notes = Annotated[str | None, StringConstraints(max_length=10000)]


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
