"""Async engine and per-request database session (research R5)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@dataclass
class Database:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]

    @classmethod
    def from_url(cls, url: str) -> Database:
        engine = create_async_engine(url, pool_pre_ping=True)
        return cls(engine, async_sessionmaker(engine, expire_on_commit=False))


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request; commits when the handler returns, before the response."""
    database: Database = request.app.state.db
    async with database.sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


# scope="function": the commit happens before the response is sent.
DbSession = Annotated[AsyncSession, Depends(get_db, scope="function")]
