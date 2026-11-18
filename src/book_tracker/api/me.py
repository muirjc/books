"""The signed-in user (allowed while a password change is pending)."""

from __future__ import annotations

from fastapi import APIRouter

from book_tracker.api import responses as r
from book_tracker.auth.dependencies import ApiUserAnyPassword
from book_tracker.schemas.auth import CurrentUser
from book_tracker.schemas.mappers import to_current_user

router = APIRouter(tags=["me"])


@router.get(
    "/me",
    response_model=CurrentUser,
    summary="The signed-in user and the session's CSRF token",
    responses=r.UNAUTHENTICATED,
)
async def me(auth: ApiUserAnyPassword) -> CurrentUser:
    return to_current_user(auth.account, auth.csrf_token)
