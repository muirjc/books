"""Sign-in and current-user schemas (contract components)."""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from book_tracker.domain.enums import Role

# At least 8 characters, no other complexity rules (FR-028). 128 bounds hashing cost.
Password = Annotated[str, Field(min_length=8, max_length=128)]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class CsrfToken(BaseModel):
    csrf_token: str


class LoginRequest(RequestModel):
    login: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class PasswordChange(RequestModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: Password


class CurrentUser(BaseModel):
    id: uuid.UUID
    display_name: str
    login: str
    role: Role
    must_change_password: bool
    csrf_token: str
