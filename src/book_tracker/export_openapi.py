"""Print the generated OpenAPI document as JSON, for the CI contract check (research R16).

``python -m book_tracker.export_openapi > generated.json``. No database connection is made.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from book_tracker.main import create_app
from book_tracker.settings import Settings


def generate() -> dict[str, Any]:
    """The app's OpenAPI document; builds the app with placeholder settings."""
    settings = Settings(
        database_url="postgresql+psycopg://placeholder@localhost/placeholder",
        # Placeholder: the export never signs anything.
        secret_key="placeholder-secret-key-for-openapi-export-only",  # noqa: S106
    )
    return create_app(settings).openapi()


def main() -> None:
    json.dump(generate(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
