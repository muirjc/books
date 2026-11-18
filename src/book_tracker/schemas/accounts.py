"""Account management schemas (contract components)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, StringConstraints, model_validator

from book_tracker.domain.enums import Role
from book_tracker.schemas.auth import Password, RequestModel


def _collapse(value: object) -> object:
    return " ".join(value.split()) if isinstance(value, str) else value


def _trim(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


DisplayName = Annotated[
    str, BeforeValidator(_collapse), StringConstraints(min_length=1, max_length=100)
]
Login = Annotated[str, BeforeValidator(_trim), StringConstraints(min_length=3, max_length=255)]


class Account(BaseModel):
    id: uuid.UUID
    display_name: str
    login: str
    role: Role
    is_active: bool
    must_change_password: bool
    created_at: datetime


class AccountCreate(RequestModel):
    """An email address is not required: a username is a valid login (FR-003)."""

    display_name: DisplayName
    login: Login
    role: Role = Role.MEMBER
    initial_password: Password


class AccountUpdate(RequestModel):
    display_name: DisplayName | None = None
    role: Role | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _something(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Change at least one field")
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} can't be empty")
        return self


class PasswordReset(RequestModel):
    temporary_password: Password
