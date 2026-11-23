"""Account management by Admins, and members changing their own password.

FR-002 – FR-005, FR-008, FR-028; research R8 (last-Admin guard) and R13 (forced change).
"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.auth import sessions
from book_tracker.auth.passwords import hash_password, verify_password
from book_tracker.domain.enums import Role
from book_tracker.domain.models import Account
from book_tracker.persistence import accounts
from book_tracker.services.errors import ConflictError, NotFoundError, WrongCurrentPassword


def _last_admin() -> ConflictError:
    return ConflictError(
        "last_admin", "This is the last active Admin. Make another member an Admin first."
    )


async def list_accounts(db: AsyncSession) -> list[Account]:
    return await accounts.list_users(db)


async def get_account(db: AsyncSession, user_id: uuid.UUID) -> Account:
    """One account, for an Admin's confirmation page (spec 014); unknown → not found."""
    account = await accounts.get_user(db, user_id)
    if account is None:
        raise NotFoundError()
    return account


async def create_account(
    db: AsyncSession, *, display_name: str, login: str, role: Role, initial_password: str
) -> Account:
    """New accounts start with a temporary password that must be changed (FR-003)."""
    try:
        async with db.begin_nested():
            return await accounts.create_user(
                db,
                display_name=display_name,
                login=login,
                password_hash=hash_password(initial_password),
                role=role.value,
                must_change_password=True,
            )
    except IntegrityError:
        raise ConflictError("login_exists", "That login is already in use") from None


async def update_account(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    display_name: str | None = None,
    role: Role | None = None,
    is_active: bool | None = None,
) -> Account:
    target = await accounts.get_user(db, user_id)
    if target is None:
        raise NotFoundError()
    losing_admin = (
        target.is_admin
        and target.is_active
        and ((role is not None and role is not Role.ADMIN) or is_active is False)
    )
    if losing_admin:
        # Lock every active Admin row so concurrent demotions can't both succeed.
        active_admins = await accounts.lock_active_admin_ids(db)
        if [admin for admin in active_admins if admin != user_id] == []:
            raise _last_admin()
    fields: dict[str, object] = {}
    if display_name is not None:
        fields["display_name"] = display_name
    if role is not None:
        fields["role"] = role.value
    if is_active is not None:
        fields["is_active"] = is_active
    updated = await accounts.update_user(db, user_id, **fields)
    if is_active is False:
        await sessions.revoke_all(db, user_id)
    return updated


async def reset_password(db: AsyncSession, user_id: uuid.UUID, temporary_password: str) -> None:
    if await accounts.get_user(db, user_id) is None:
        raise NotFoundError()
    await accounts.update_user(
        db, user_id, password_hash=hash_password(temporary_password), must_change_password=True
    )
    await sessions.revoke_all(db, user_id)


async def change_own_password(
    db: AsyncSession,
    account: Account,
    session_id: uuid.UUID,
    current_password: str,
    new_password: str,
) -> Account:
    if not verify_password(account.password_hash, current_password):
        raise WrongCurrentPassword()
    updated = await accounts.update_user(
        db, account.id, password_hash=hash_password(new_password), must_change_password=False
    )
    await sessions.revoke_all(db, account.id, keep_session_id=session_id)
    return updated
