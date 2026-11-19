"""Database rules for spec 002's tables (data-model.md; Principle VI; task T007)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from tests.conftest import Factory, TestUser

INSERT_REF = (
    "INSERT INTO book_source_ref (id, book_id, source, source_work_id, imported_by) "
    "VALUES (:id, :book, :source, :work, :user)"
)
INSERT_CACHE = (
    "INSERT INTO source_lookup_cache (source, kind, lookup_key, payload, fetched_at, expires_at) "
    "VALUES (:source, :kind, :key, '{}'::jsonb, now(), :expires)"
)


async def _ref(factory: Factory, book: uuid.UUID, user: TestUser, **over: Any) -> None:
    params = {"id": uuid.uuid4(), "book": book, "source": "open_library", "work": "OL1W"}
    params.update(over)
    await factory.execute(INSERT_REF, user=user.id, **params)


async def _violates(constraint: str, action: Any) -> None:
    with pytest.raises(IntegrityError) as excinfo:
        await action
    assert constraint in str(excinfo.value)


async def test_one_catalog_book_per_source_work(factory: Factory) -> None:
    alice = await factory.user("alice")
    first, second = await factory.book("A", alice), await factory.book("B", alice)
    await _ref(factory, first, alice, work="OL1W")
    await _violates("book_source_ref_source_work_key", _ref(factory, second, alice, work="OL1W"))


async def test_one_ref_per_book_and_source(factory: Factory) -> None:
    alice = await factory.user("alice")
    book = await factory.book("A", alice)
    await _ref(factory, book, alice, work="OL1W")
    await _violates("book_source_ref_book_source_key", _ref(factory, book, alice, work="OL2W"))


async def test_open_library_ids_have_the_work_format(factory: Factory) -> None:
    alice = await factory.user("alice")
    book = await factory.book("A", alice)
    await _violates(
        "book_source_ref_open_library_id_format", _ref(factory, book, alice, work="abc")
    )


async def test_only_approved_sources(factory: Factory) -> None:
    alice = await factory.user("alice")
    book = await factory.book("A", alice)
    await _violates(
        "book_source_ref_source_check", _ref(factory, book, alice, source="google_books")
    )
    await _violates(
        "source_lookup_cache_source_check",
        factory.execute(
            INSERT_CACHE, source="google_books", kind="author_search", key="x", expires="2100-01-01"
        ),
    )


async def test_cache_kind_and_expiry(factory: Factory) -> None:
    await _violates(
        "source_lookup_cache_kind_check",
        factory.execute(
            INSERT_CACHE, source="open_library", kind="other", key="x", expires="2100-01-01"
        ),
    )
    await _violates(
        "source_lookup_cache_expiry_check",
        factory.execute(
            INSERT_CACHE, source="open_library", kind="author_search", key="x", expires="2000-01-01"
        ),
    )


async def test_deleting_a_book_deletes_its_source_ref(factory: Factory) -> None:
    alice = await factory.user("alice")
    book = await factory.book("A", alice)
    await _ref(factory, book, alice)
    await factory.execute("DELETE FROM book_author WHERE book_id = :b", b=book)
    await factory.execute("DELETE FROM book WHERE id = :b", b=book)
    assert await factory.scalar("SELECT count(*) FROM book_source_ref") == 0
