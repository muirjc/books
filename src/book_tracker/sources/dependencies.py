"""The app's book source as a FastAPI dependency (spec 002 task T021).

Kept here, not in ``auth/dependencies.py``, so that coverage-critical module is unchanged.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from book_tracker.sources.base import BookSource


def book_source(request: Request) -> BookSource:
    source: BookSource = request.app.state.book_source
    return source


BookSourceDep = Annotated[BookSource, Depends(book_source)]
