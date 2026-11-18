"""Account management for Admins (FR-003 – FR-005). No route here returns reading entries."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response

from book_tracker.api import responses as r
from book_tracker.auth.dependencies import ApiAdmin
from book_tracker.persistence.db import DbSession
from book_tracker.schemas.accounts import Account, AccountCreate, AccountUpdate, PasswordReset
from book_tracker.schemas.mappers import account_out
from book_tracker.services import accounts as service

router = APIRouter(prefix="/admin/users", tags=["admin"])


@router.get(
    "",
    response_model=list[Account],
    summary="List accounts; Admin only",
    responses=r.merge(r.UNAUTHENTICATED, r.FORBIDDEN),
)
async def list_accounts(auth: ApiAdmin, db: DbSession) -> list[Account]:
    return [account_out(a) for a in await service.list_accounts(db)]


@router.post(
    "",
    response_model=Account,
    status_code=201,
    summary="Create an account; Admin only",
    responses=r.merge(r.UNAUTHENTICATED, r.FORBIDDEN, r.PLAIN_CONFLICT, r.VALIDATION),
)
async def create_account(body: AccountCreate, auth: ApiAdmin, db: DbSession) -> Account:
    account = await service.create_account(
        db,
        display_name=body.display_name,
        login=body.login,
        role=body.role,
        initial_password=body.initial_password,
    )
    return account_out(account)


@router.patch(
    "/{user_id}",
    response_model=Account,
    summary="Change display name, role or active state; Admin only",
    responses=r.merge(r.UNAUTHENTICATED, r.FORBIDDEN, r.NOT_FOUND, r.PLAIN_CONFLICT, r.VALIDATION),
)
async def update_account(
    user_id: uuid.UUID, body: AccountUpdate, auth: ApiAdmin, db: DbSession
) -> Account:
    account = await service.update_account(
        db, user_id, display_name=body.display_name, role=body.role, is_active=body.is_active
    )
    return account_out(account)


@router.post(
    "/{user_id}/password-reset",
    status_code=204,
    summary="Set a temporary password; Admin only",
    responses=r.merge(r.UNAUTHENTICATED, r.FORBIDDEN, r.NOT_FOUND, r.VALIDATION),
)
async def reset_password(
    user_id: uuid.UUID, body: PasswordReset, auth: ApiAdmin, db: DbSession
) -> Response:
    await service.reset_password(db, user_id, body.temporary_password)
    return Response(status_code=204)
