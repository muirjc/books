"""The ``ac`` marker accepts acceptance criteria from any feature (spec 002, task T001)."""

from __future__ import annotations

import pytest

from tests.conftest import AC_ID


@pytest.mark.parametrize("ac_id", ["001/AC-01", "001/AC-35", "002/AC-01", "002/AC-23"])
def test_feature_qualified_ids_are_accepted(ac_id: str) -> None:
    assert AC_ID.match(ac_id)


@pytest.mark.parametrize("ac_id", ["2/AC-1", "002/AC-1", "002/FR-01", "AC-01", "002/ac-01"])
def test_other_shapes_are_rejected(ac_id: str) -> None:
    assert not AC_ID.match(ac_id)
