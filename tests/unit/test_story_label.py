"""Spec 019: a story's label with and without a series."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from book_tracker.domain.models import SeriesRef, Story, UserRef
from book_tracker.services.catalog import story_label


def _story(series: SeriesRef | None, number: Decimal | None) -> Story:
    who = UserRef(id=uuid.uuid4(), display_name="A")
    now = datetime(2026, 11, 26, tzinfo=UTC)
    return Story(uuid.uuid4(), "The Lottery", (), series, number, (), who, now, who, now)


@pytest.mark.ac("019/AC-08")
def test_story_label() -> None:
    dresden = SeriesRef(id=uuid.uuid4(), name="The Dresden Files")
    assert story_label(_story(dresden, Decimal("2.50"))) == "#2.5 The Lottery"
    assert story_label(_story(None, None)) == "The Lottery"
