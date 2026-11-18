"""T045: times-read rules (FR-029)."""

from __future__ import annotations

import pytest

from book_tracker.domain.enums import ReadingStatus as S
from book_tracker.services.readings import apply_status_change


@pytest.mark.ac("001/AC-31")
def test_adding() -> None:
    assert apply_status_change(None, S.FINISHED, 0, None) == 1
    assert apply_status_change(None, S.WANT_TO_READ, 0, None) == 0
    assert apply_status_change(None, S.READING, 0, None) == 0
    assert apply_status_change(None, S.FINISHED, 0, 4) == 4


@pytest.mark.ac("001/AC-35")
def test_change_into_finished_adds_one() -> None:
    assert apply_status_change(S.READING, S.FINISHED, 1, None) == 2
    assert apply_status_change(S.WANT_TO_READ, S.FINISHED, 0, None) == 1


def test_capped_at_99() -> None:
    assert apply_status_change(S.READING, S.FINISHED, 99, None) == 99


@pytest.mark.ac("001/AC-35")
def test_other_changes_keep_count() -> None:
    assert apply_status_change(S.FINISHED, S.READING, 1, None) == 1  # read again
    assert apply_status_change(S.FINISHED, S.FINISHED, 3, None) == 3
    assert apply_status_change(S.READING, S.WANT_TO_READ, 2, None) == 2


def test_explicit_count_replaces_increment() -> None:
    assert apply_status_change(S.READING, S.FINISHED, 1, 5) == 5
    assert apply_status_change(S.FINISHED, S.FINISHED, 1, 0) == 0
