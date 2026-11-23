"""Errors raised by services and auth guards. ``api/errors.py`` maps them to HTTP.

This module imports nothing from ``api/`` so the service layer never depends on the web
layer (Constitution Principle VII).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from book_tracker.domain.models import Story


class ServiceError(Exception):
    code: str = "error"
    title: str = "Something went wrong"

    def __init__(self, code: str | None = None, title: str | None = None) -> None:
        if code is not None:
            self.code = code
        if title is not None:
            self.title = title
        super().__init__(self.title)


class NotFoundError(ServiceError):
    """Missing, or belongs to another member: the two are indistinguishable (FR-020)."""

    code = "not_found"
    title = "Not found"


class ConflictError(ServiceError):
    def __init__(
        self,
        code: str,
        title: str,
        existing_id: uuid.UUID | None = None,
        existing_label: str | None = None,
    ) -> None:
        super().__init__(code, title)
        self.existing_id = existing_id
        self.existing_label = existing_label


class StoryNumberTaken(ConflictError):
    """Item ``index`` of a new book's stories is at a series and number another story
    holds (spec 013 AC-13, AC-16, AC-25)."""

    def __init__(self, index: int, story: Story, label: str) -> None:
        super().__init__(
            "story_number_taken",
            "Another story already has this number in the series",
            existing_id=story.id,
            existing_label=label,
        )
        self.index = index
        self.story = story


class SourceUnavailable(ServiceError):
    """Open Library timed out, refused or failed; nothing was changed (spec 002 AC-13)."""

    code = "source_unavailable"
    title = "The book site couldn't be reached. Try again later, or add the book by hand."


class SourceNotFound(NotFoundError):
    """Open Library has no author with this key (spec 002 AC-23)."""

    code = "author_not_found"
    title = "No such author on Open Library"


class ForbiddenError(ServiceError):
    code = "forbidden"
    title = "You can't do this"


@dataclass(frozen=True)
class FieldError:
    field: str
    message: str


class ValidationFailed(ServiceError):
    code = "validation_failed"
    title = "Some fields need attention"

    def __init__(self, errors: list[FieldError]) -> None:
        super().__init__()
        self.errors = errors

    @classmethod
    def single(cls, field: str, message: str) -> ValidationFailed:
        return cls([FieldError(field, message)])


class NotAuthenticated(ServiceError):
    code = "not_authenticated"
    title = "Sign in to continue"


class PasswordChangeRequired(ServiceError):
    code = "password_change_required"
    title = "Choose a new password to continue"


class CsrfFailed(ForbiddenError):
    code = "csrf_failed"
    title = "This form has expired or came from another site. Reload the page and try again."


class NotAdmin(ForbiddenError):
    code = "not_admin"
    title = "Only an Admin can do this"


class InvalidCredentials(ServiceError):
    """Wrong login, wrong password and deactivated account all look the same (FR-002)."""

    code = "invalid_credentials"
    title = "Wrong login or password"


class TooManyAttempts(ServiceError):
    code = "too_many_attempts"
    title = "Too many attempts. Try again later."

    def __init__(self, retry_after: int) -> None:
        super().__init__()
        self.retry_after = retry_after


class WrongCurrentPassword(ServiceError):
    code = "wrong_current_password"
    title = "Your current password is wrong"


# --------------------------------------------------------------------------- spec 012
# Titles are the messages members see (AC-09); each one leaves hand-writing open.


class AiNotConfigured(ServiceError):
    code = "ai_not_configured"
    title = "AI drafts aren't set up. You can write the summary yourself."


class AiUnavailable(ServiceError):
    code = "ai_unavailable"
    title = "The AI didn't answer in time. Try again, or write the summary yourself."


class AiDeclined(ServiceError):
    code = "ai_declined"
    title = "The AI couldn't write a summary of this book. You can write one yourself."


class NotEnoughInformation(ServiceError):
    code = "not_enough_information"
    title = (
        "The AI couldn't find enough about this book to write a summary. "
        "You can write one yourself."
    )


class DraftRejected(ServiceError):
    code = "draft_rejected"
    title = "The AI's draft didn't pass our checks. Try again, or write the summary yourself."


class DraftLimitReached(ServiceError):
    code = "draft_limit_reached"

    def __init__(self, limit: int) -> None:
        super().__init__(
            title=f"You've used your {limit} AI drafts for today. You can write the summary "
            "yourself, or draft again tomorrow."
        )
        self.limit = limit
