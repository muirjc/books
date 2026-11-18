"""Sign-in endpoints of the JSON API (FR-001, FR-002, FR-027)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from book_tracker.api import responses as r
from book_tracker.auth import csrf
from book_tracker.auth.dependencies import ApiUserAnyPassword, now
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.auth import CsrfToken, CurrentUser, LoginRequest, PasswordChange
from book_tracker.schemas.mappers import to_current_user
from book_tracker.services import accounts as accounts_service
from book_tracker.services import auth as auth_service
from book_tracker.services.errors import CsrfFailed
from book_tracker.web.cookies import (
    clear_session_cookie,
    remember_profile,
    set_presession_cookie,
    set_session_cookie,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def secret(request: Request) -> str:
    value: str = request.app.state.settings.secret_key.get_secret_value()
    return value


@router.get("/csrf", response_model=CsrfToken, summary="Get a pre-session CSRF token for sign-in")
async def get_csrf(request: Request, response: Response) -> CsrfToken:
    token = csrf.issue(secret(request))
    set_presession_cookie(response, token)
    return CsrfToken(csrf_token=token)


@router.post(
    "/login",
    response_model=CurrentUser,
    summary="Sign in (FR-001, FR-027)",
    responses=r.merge(r.LOGIN_FAILED, r.CSRF_FAILED, r.VALIDATION, r.TOO_MANY_ATTEMPTS),
)
async def login(
    body: LoginRequest, request: Request, response: Response, db: DbSession
) -> CurrentUser:
    if not csrf.verify(
        secret(request),
        request.cookies.get(csrf.PRESESSION_COOKIE),
        request.headers.get("x-csrf-token"),
    ):
        raise CsrfFailed()
    settings = request.app.state.settings
    signed = await auth_service.sign_in(
        db, body.login, body.password, now(request), settings.session_idle_days, secret(request)
    )
    set_session_cookie(response, signed.token, settings.session_idle_days)
    remember_profile(request, response, signed.account.id)
    response.delete_cookie(
        csrf.PRESESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax"
    )
    return to_current_user(signed.account, signed.csrf_token)


@router.post(
    "/logout",
    status_code=204,
    summary="Sign out; ends the current session",
    responses=r.merge(r.UNAUTHENTICATED, r.CSRF_FAILED),
)
async def logout(auth: ApiUserAnyPassword, db: DbSession) -> Response:
    await auth_service.sign_out(db, auth.session_token)
    response = Response(status_code=204)
    clear_session_cookie(response)
    return response


@router.post(
    "/password",
    status_code=204,
    summary="Change my password; ends my other sessions (FR-004, FR-028)",
    responses=r.merge(r.BAD_REQUEST, r.UNAUTHENTICATED, r.CSRF_FAILED, r.VALIDATION),
)
async def change_password(
    body: PasswordChange, auth: ApiUserAnyPassword, db: DbSession
) -> Response:
    await accounts_service.change_own_password(
        db, auth.account, auth.session_id, body.current_password, body.new_password
    )
    return Response(status_code=204)
