"""Sign-in, sign-out, switch user and change-password pages (FR-001, FR-004, FR-007)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import TypeAdapter, ValidationError
from starlette.responses import Response

from book_tracker.auth import csrf
from book_tracker.auth.dependencies import Authenticated, UiUserAnyPassword, now
from book_tracker.persistence import accounts
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.auth import Password
from book_tracker.services import accounts as accounts_service
from book_tracker.services import auth as auth_service
from book_tracker.services.errors import InvalidCredentials, ServiceError, WrongCurrentPassword
from book_tracker.web.cookies import (
    clear_session_cookie,
    recent_profile_ids,
    remember_profile,
    set_presession_cookie,
    set_session_cookie,
)
from book_tracker.web.forms import text
from book_tracker.web.rendering import render, render_error

router = APIRouter(include_in_schema=False)

_password = TypeAdapter(Password)


@dataclass(frozen=True, slots=True)
class Profile:
    display_name: str
    login: str


def _secret(request: Request) -> str:
    value: str = request.app.state.settings.secret_key.get_secret_value()
    return value


async def recent_profiles_for(request: Request, db: DbSession) -> list[Profile]:
    """Active accounts recently used on this device, most recent first (FR-007)."""
    ids = recent_profile_ids(request)
    by_id = {a.id: a for a in await accounts.get_users(db, ids)}
    return [
        Profile(by_id[i].display_name, by_id[i].login)
        for i in ids
        if i in by_id and by_id[i].is_active
    ]


async def sign_in_page(
    request: Request,
    db: DbSession,
    *,
    login: str = "",
    error: str | None = None,
    status_code: int = 200,
) -> Response:
    token = csrf.issue(_secret(request))
    response = render(
        request,
        "pages/sign_in.html",
        {
            "presession_token": token,
            "login": login,
            "error": error,
            "recent_profiles": await recent_profiles_for(request, db),
        },
        status_code=status_code,
    )
    set_presession_cookie(response, token)
    return response


@router.get("/sign-in")
async def get_sign_in(request: Request, db: DbSession) -> Response:
    return await sign_in_page(request, db)


@router.post("/sign-in")
async def post_sign_in(request: Request, db: DbSession) -> Response:
    form = await request.form()
    login, token = text(form, "login"), text(form, "csrf_token")
    password = form.get("password")
    if not csrf.verify(_secret(request), request.cookies.get(csrf.PRESESSION_COOKIE), token):
        return render_error(request, 403, "This form has expired. Reload the page and try again.")
    settings = request.app.state.settings
    try:
        signed = await auth_service.sign_in(
            db,
            login,
            password if isinstance(password, str) else "",
            now(request),
            settings.session_idle_days,
            _secret(request),
        )
    except InvalidCredentials as exc:
        return await sign_in_page(request, db, login=login, error=exc.title, status_code=401)
    except ServiceError as exc:
        status = 429 if exc.code == "too_many_attempts" else 400
        return await sign_in_page(request, db, login=login, error=exc.title, status_code=status)
    target = "/account/password" if signed.account.must_change_password else "/"
    response = RedirectResponse(target, status_code=303)
    set_session_cookie(response, signed.token, settings.session_idle_days)
    response.delete_cookie(
        csrf.PRESESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax"
    )
    remember_profile(request, response, signed.account.id)
    return response


async def _end_session(auth: Authenticated, db: DbSession) -> Response:
    await auth_service.sign_out(db, auth.session_token)
    response = RedirectResponse("/sign-in", status_code=303)
    clear_session_cookie(response)
    return response


@router.post("/sign-out")
async def post_sign_out(auth: UiUserAnyPassword, db: DbSession) -> Response:
    return await _end_session(auth, db)


@router.post("/switch-user")
async def post_switch_user(auth: UiUserAnyPassword, db: DbSession) -> Response:
    """Sign out but keep the device's recent profiles, so the next person can pick theirs."""
    return await _end_session(auth, db)


# --------------------------------------------------------------------------- password


def _password_page(
    request: Request,
    auth: Authenticated,
    errors: dict[str, str] | None = None,
    status_code: int = 200,
) -> Response:
    return render(
        request,
        "pages/change_password.html",
        {"errors": errors or {}, "forced": auth.account.must_change_password},
        auth=auth,
        status_code=status_code,
    )


@router.get("/account/password")
async def get_change_password(request: Request, auth: UiUserAnyPassword) -> Response:
    return _password_page(request, auth)


@router.post("/account/password")
async def post_change_password(
    request: Request, auth: UiUserAnyPassword, db: DbSession
) -> Response:
    form = await request.form()
    current = form.get("current_password")
    new = form.get("new_password")
    repeat = form.get("repeat_password")
    errors: dict[str, str] = {}
    if not isinstance(current, str) or not current:
        errors["current_password"] = "Enter your current password"  # noqa: S105 - a message, not a password
    try:
        _password.validate_python(new if isinstance(new, str) else "")
    except ValidationError:
        errors["new_password"] = "The new password must be at least 8 characters"  # noqa: S105 - a message, not a password
    if "new_password" not in errors and new != repeat:
        errors["repeat_password"] = "The new passwords don't match"  # noqa: S105 - a message, not a password
    if errors or not isinstance(current, str) or not isinstance(new, str):
        return _password_page(request, auth, errors, status_code=422)
    try:
        await accounts_service.change_own_password(db, auth.account, auth.session_id, current, new)
    except WrongCurrentPassword as exc:
        return _password_page(request, auth, {"current_password": exc.title}, status_code=400)
    return RedirectResponse("/?msg=password", status_code=303)
