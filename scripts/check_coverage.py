"""Fail unless every coverage-critical module has 100% line coverage.

Run after ``pytest --cov --cov-report=json``. The module list comes from the
"Coverage-critical modules" sections of specs/001-family-reading-list/plan.md and
specs/002-author-book-import/plan.md (Constitution Principle V).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CRITICAL_MODULES = (
    "src/book_tracker/auth/sessions.py",
    "src/book_tracker/auth/dependencies.py",
    "src/book_tracker/auth/throttle.py",
    "src/book_tracker/persistence/readings.py",
    "src/book_tracker/persistence/favorites.py",  # spec 011: personal favorites
    "src/book_tracker/services/accounts.py",
    "src/book_tracker/services/imports.py",  # spec 002: whose list receives imported books
)


def main(report_path: str = "coverage.json") -> int:
    path = Path(report_path)
    if not path.exists():
        print(f"{report_path} not found: run pytest --cov --cov-report=json first")
        return 2
    files = json.loads(path.read_text())["files"]
    failures: list[str] = []
    for module in CRITICAL_MODULES:
        entry = files.get(module)
        if entry is None:
            failures.append(f"{module}: not measured")
            continue
        missing = entry["missing_lines"]
        if missing:
            percent = entry["summary"]["percent_covered_display"]
            failures.append(f"{module}: {percent}% (missing lines {missing})")
    if failures:
        print("Coverage-critical modules below 100% line coverage:")
        for line in failures:
            print(f"  {line}")
        return 1
    print(f"All {len(CRITICAL_MODULES)} coverage-critical modules at 100% line coverage.")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
