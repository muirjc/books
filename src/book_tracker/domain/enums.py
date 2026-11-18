"""Enumerations shared by every layer."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    MEMBER = "member"
    ADMIN = "admin"


class ReadingStatus(StrEnum):
    WANT_TO_READ = "want_to_read"
    READING = "reading"
    FINISHED = "finished"


class SummaryOrigin(StrEnum):
    AI = "ai"
    AI_EDITED = "ai_edited"
    MANUAL = "manual"
