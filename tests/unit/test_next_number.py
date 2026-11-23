"""Spec 014 AC-12: the series page's Add #next number."""

from __future__ import annotations

from decimal import Decimal

import pytest

from book_tracker.services.readings import next_number


@pytest.mark.ac("014/AC-12")
@pytest.mark.parametrize(
    ("numbers", "expected"),
    [
        ({"1", "2"}, 3),
        ({"1", "3.5"}, 4),  # a fraction rounds down, then the next whole number
        ({"998.5"}, 999),
        ({"999"}, None),  # past the highest number a book can have
        ({"999.5"}, None),
        (set(), None),  # nothing numbered
    ],
)
def test_next_number(numbers: set[str], expected: int | None) -> None:
    assert next_number({Decimal(n) for n in numbers}) == expected
