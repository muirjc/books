"""The AI behind summary drafts (spec 012 research R9; Constitution Principle III).

Services see only this protocol, so the provider can be swapped and tests use a fake.
Failures raise ``AiNotConfigured``, ``AiUnavailable`` or ``AiDeclined``.
"""

from __future__ import annotations

from typing import Annotated, Protocol

from fastapi import Depends, Request

from book_tracker.domain.drafts import BookDescription, BookFacts, GeneratedDraft
from book_tracker.services.errors import AiNotConfigured


class SummaryGenerator(Protocol):
    configured: bool  # False: drafting says "not set up" before any allowance is spent

    async def draft(self, facts: BookFacts, description: BookDescription | None) -> GeneratedDraft:
        """A draft from the book's facts and Open Library's description, if any."""
        ...


class UnconfiguredGenerator:
    """Installed when the server has no AI key: every request says so, with no network."""

    configured = False

    async def draft(self, facts: BookFacts, description: BookDescription | None) -> GeneratedDraft:
        raise AiNotConfigured()


def summary_generator(request: Request) -> SummaryGenerator:
    generator: SummaryGenerator = request.app.state.summary_generator
    return generator


SummaryGeneratorDep = Annotated[SummaryGenerator, Depends(summary_generator)]
