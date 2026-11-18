"""The committed generated-OpenAPI baseline is current (research R16, CI contract check).

CI compares each change's generated document with the base branch's committed baseline using
``oasdiff breaking``, so the baseline must be regenerated whenever the API changes:

    uv run python -m book_tracker.export_openapi \\
        > specs/001-family-reading-list/contracts/openapi.generated.json
"""

from __future__ import annotations

import json
from pathlib import Path

from book_tracker.export_openapi import generate

BASELINE = (
    Path(__file__).resolve().parents[2]
    / "specs"
    / "001-family-reading-list"
    / "contracts"
    / "openapi.generated.json"
)


def test_baseline_matches_generated_document() -> None:
    assert BASELINE.exists(), "commit the generated OpenAPI baseline"
    assert json.loads(BASELINE.read_text()) == generate(), (
        "The API changed: regenerate contracts/openapi.generated.json (see module docstring)"
    )
