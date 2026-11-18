"""T015: domain value rules."""

from __future__ import annotations

from decimal import Decimal

import pytest

from book_tracker.domain.values import (
    default_sort_name,
    format_series_number,
    normalize_name,
    parse_isbn13,
    parse_series_number,
)


@pytest.mark.ac("001/AC-30")
@pytest.mark.parametrize("raw", ["978-0-306-40615-7", "978 0 306 40615 7", "9780306406157"])
def test_isbn13_accepts_and_normalizes(raw: str) -> None:
    assert parse_isbn13(raw) == "9780306406157"


@pytest.mark.ac("001/AC-30")
@pytest.mark.parametrize(
    "raw", ["9780306406158", "978030640615", "97803064061570", "97803064A6157", ""]
)
def test_isbn13_rejects_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_isbn13(raw)


@pytest.mark.ac("001/AC-20")
@pytest.mark.parametrize(
    "raw,expected",
    [("0", "0"), ("2.5", "2.5"), ("999.99", "999.99"), ("3", "3"), ("2.50", "2.5"), (" 7 ", "7")],
)
def test_series_number_accepts(raw: str, expected: str) -> None:
    assert parse_series_number(raw) == Decimal(expected)


@pytest.mark.ac("001/AC-20")
@pytest.mark.parametrize("raw", ["-1", "1000", "2.555", "abc", "1e2", "NaN", ""])
def test_series_number_rejects(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_series_number(raw)


@pytest.mark.parametrize(
    "value,text",
    [
        (Decimal("2.50"), "2.5"),
        (Decimal("3.00"), "3"),
        (Decimal("10"), "10"),
        (Decimal("0.00"), "0"),
        (Decimal("999.99"), "999.99"),
    ],
)
def test_format_series_number(value: Decimal, text: str) -> None:
    assert format_series_number(value) == text


def test_normalize_name() -> None:
    assert normalize_name("  Terry   Pratchett \t") == "Terry Pratchett"


def test_default_sort_name() -> None:
    assert default_sort_name("J.K. Rowling") == "Rowling, J.K."
    assert default_sort_name("Ursula K. Le Guin") == "Guin, Ursula K. Le"
    assert default_sort_name("Homer") == "Homer"
