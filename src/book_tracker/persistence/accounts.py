"""Account and session rows. Returns domain objects only."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from book_tracker.domain.models import Account
from book_tracker.persistence import models
from book_tracker.persistence.mappers import to_account

# --------------------------------------------------------------------------- users


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> Account | None:
    row = await db.get(models.AppUser, user_id)
    return to_account(row) if row else None


async def get_user_by_login(db: AsyncSession, login: str) -> Account | None:
    row = (
        await db.execute(
            select(models.AppUser).where(func.lower(models.AppUser.login) == login.strip().lower())
        )
    ).scalar_one_or_none()
    return to_account(row) if row else None


async def get_users(db: AsyncSession, user_ids: list[uuid.UUID]) -> list[Account]:
    if not user_ids:
        return []
    rows = (
        (await db.execute(select(models.AppUser).where(models.AppUser.id.in_(user_ids))))
        .scalars()
        .all()
    )
    return [to_account(row) for row in rows]


async def list_users(db: AsyncSession) -> list[Account]:
    rows = (
        (await db.execute(select(models.AppUser).order_by(func.lower(models.AppUser.display_name))))
        .scalars()
        .all()
    )
    return [to_account(row) for row in rows]


async def create_user(
    db: AsyncSession,
    *,
    display_name: str,
    login: str,
    password_hash: str,
    role: str,
    must_change_password: bool,
) -> Account:
    row = models.AppUser(
        id=uuid.uuid4(),
        display_name=display_name,
        login=login,
        password_hash=password_hash,
        role=role,
        is_active=True,
        must_change_password=must_change_password,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return to_account(row)


async def update_user(db: AsyncSession, user_id: uuid.UUID, **fields: object) -> Account:
    await db.execute(
        update(models.AppUser)
        .where(models.AppUser.id == user_id)
        .values(**fields, updated_at=func.now())
    )
    row = (
        await db.execute(
            select(models.AppUser)
            .where(models.AppUser.id == user_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    return to_account(row)


async def lock_active_admin_ids(db: AsyncSession) -> list[uuid.UUID]:
    """Lock every active Admin row for the rest of the transaction (research R8)."""
    rows = (
        (
            await db.execute(
                select(models.AppUser.id)
                .where(models.AppUser.role == "admin", models.AppUser.is_active)
                .order_by(models.AppUser.id)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def admin_exists(db: AsyncSession) -> bool:
    count = (
        await db.execute(
            select(func.count()).select_from(models.AppUser).where(models.AppUser.role == "admin")
        )
    ).scalar_one()
    return bool(count)


# --------------------------------------------------------------------------- sessions


async def insert_session(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    token_hash: str,
    csrf_token: str,
    now: datetime,
    expires_at: datetime,
) -> uuid.UUID:
    row = models.UserSession(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        csrf_token=csrf_token,
        last_seen_at=now,
        expires_at=expires_at,
    )
    db.add(row)
    await db.flush()
    return row.id


async def find_session(
    db: AsyncSession, token_hash: str
) -> tuple[models.UserSession, Account] | None:
    row = (
        await db.execute(
            select(models.UserSession)
            .where(models.UserSession.token_hash == token_hash)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return row, to_account(row.user)


async def touch_session(
    db: AsyncSession, session_id: uuid.UUID, now: datetime, expires_at: datetime
) -> None:
    await db.execute(
        update(models.UserSession)
        .where(models.UserSession.id == session_id)
        .values(last_seen_at=now, expires_at=expires_at, updated_at=func.now())
    )


async def delete_session(db: AsyncSession, token_hash: str) -> None:
    await db.execute(delete(models.UserSession).where(models.UserSession.token_hash == token_hash))


async def delete_user_sessions(
    db: AsyncSession, user_id: uuid.UUID, keep_session_id: uuid.UUID | None = None
) -> None:
    statement = delete(models.UserSession).where(models.UserSession.user_id == user_id)
    if keep_session_id is not None:
        statement = statement.where(models.UserSession.id != keep_session_id)
    await db.execute(statement)
