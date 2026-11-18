"""Account management pages for Admins (FR-003 – FR-005). They never show reading entries."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from starlette.responses import Response

from book_tracker.auth.dependencies import Authenticated, UiAdmin
from book_tracker.domain.enums import Role
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.accounts import AccountCreate, PasswordReset
from book_tracker.services import accounts as service
from book_tracker.services.errors import ConflictError
from book_tracker.web.forms import text
from book_tracker.web.rendering import render

router = APIRouter(prefix="/admin/users", include_in_schema=False)

MESSAGES = {
    "created": "Account created. Tell the member their temporary password.",
    "updated": "Account updated.",
    "reset": "Password reset. Tell the member their temporary password.",
}
ACTIONS: dict[str, dict[str, Any]] = {
    "deactivate": {"is_active": False},
    "reactivate": {"is_active": True},
    "make_admin": {"role": Role.ADMIN},
    "make_member": {"role": Role.MEMBER},
}
CREATE_MESSAGES = {
    "display_name": "Enter a display name of up to 100 characters",
    "login": "Enter a username or email address of 3 to 255 characters",
    "role": "Choose Member or Admin",
    "initial_password": "The password must be at least 8 characters",
}


async def _users_page(
    request: Request,
    auth: Authenticated,
    db: DbSession,
    *,
    error: str | None = None,
    reset_errors: dict[str, str] | None = None,
    status_code: int = 200,
) -> Response:
    return render(
        request,
        "admin/users.html",
        {
            "accounts": await service.list_accounts(db),
            "message": MESSAGES.get(request.query_params.get("msg", "")),
            "error": error,
            "reset_errors": reset_errors or {},
            "active": "admin",
        },
        auth=auth,
        status_code=status_code,
    )


@router.get("")
async def list_users(request: Request, auth: UiAdmin, db: DbSession) -> Response:
    return await _users_page(request, auth, db)


def _new_user_page(
    request: Request,
    auth: Authenticated,
    values: dict[str, str] | None = None,
    errors: dict[str, str] | None = None,
    status_code: int = 200,
) -> Response:
    return render(
        request,
        "admin/new_user.html",
        {"values": values or {}, "errors": errors or {}, "active": "admin"},
        auth=auth,
        status_code=status_code,
    )


@router.get("/new")
async def new_user_form(request: Request, auth: UiAdmin) -> Response:
    return _new_user_page(request, auth)


@router.post("/new")
async def create_user(request: Request, auth: UiAdmin, db: DbSession) -> Response:
    form = await request.form()
    values = {name: text(form, name) for name in ("display_name", "login", "role")}
    raw_password = form.get("initial_password")
    try:
        body = AccountCreate.model_validate(
            {
                **values,
                "role": values["role"] or Role.MEMBER.value,
                "initial_password": raw_password if isinstance(raw_password, str) else "",
            }
        )
    except ValidationError as exc:
        errors = {
            str(e["loc"][0]): CREATE_MESSAGES.get(str(e["loc"][0]), "Check this field")
            for e in exc.errors()
            if e["loc"]
        }
        return _new_user_page(request, auth, values, errors, status_code=422)
    try:
        await service.create_account(
            db,
            display_name=body.display_name,
            login=body.login,
            role=body.role,
            initial_password=body.initial_password,
        )
    except ConflictError as exc:
        await db.rollback()
        return _new_user_page(request, auth, values, {"login": exc.title}, status_code=409)
    return RedirectResponse("/admin/users?msg=created", status_code=303)


@router.post("/{user_id}")
async def update_user(
    user_id: uuid.UUID, request: Request, auth: UiAdmin, db: DbSession
) -> Response:
    form = await request.form()
    changes = ACTIONS.get(text(form, "action"))
    if changes is None:
        return await _users_page(request, auth, db, error="Choose an action", status_code=422)
    try:
        await service.update_account(db, user_id, **changes)
    except ConflictError as exc:
        await db.rollback()
        return await _users_page(request, auth, db, error=exc.title, status_code=409)
    return RedirectResponse("/admin/users?msg=updated", status_code=303)


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: uuid.UUID, request: Request, auth: UiAdmin, db: DbSession
) -> Response:
    form = await request.form()
    raw = form.get("temporary_password")
    try:
        body = PasswordReset.model_validate(
            {"temporary_password": raw if isinstance(raw, str) else ""}
        )
    except ValidationError:
        return await _users_page(
            request,
            auth,
            db,
            reset_errors={str(user_id): "The temporary password must be at least 8 characters"},
            status_code=422,
        )
    await service.reset_password(db, user_id, body.temporary_password)
    return RedirectResponse("/admin/users?msg=reset", status_code=303)
