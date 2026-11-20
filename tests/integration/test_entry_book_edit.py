"""Edit the book's details from its entry page (books-4l5).

The entry page offers every book field (title, authors, series, number, ISBN) beside the
member's own status, date, times read and notes, saved by one button. Book details are
shared with the family; reading details stay private.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice", display_name="Alice")


@pytest.fixture
async def member(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


async def _setup(factory: Factory, alice: TestUser) -> dict[str, Any]:
    ben = await factory.user("ben", display_name="Ben")
    author = await factory.author("Terry Pratchett", ben)
    series = await factory.series("Discworld", ben)
    book = await factory.book(
        "Mortt", ben, author_ids=[author], series_id=series, series_number="4"
    )
    entry = await factory.entry(alice, book, notes="Old note")
    return {"ben": ben, "author": author, "series": series, "book": book, "entry": entry}


def _form(s: dict[str, Any], **overrides: str) -> dict[str, str]:
    data = {
        "title": "Mortt",
        "author_name_0": "Terry Pratchett",
        "author_id_0": str(s["author"]),
        "series_name": "Discworld",
        "series_id": str(s["series"]),
        "series_number": "4",
        "isbn_13": "",
        "status": "finished",
        "finished_on": "",
        "times_read": "1",
        "notes": "Old note",
    }
    data.update(overrides)
    return data


async def _book(factory: Factory, book: uuid.UUID) -> tuple[str, str]:
    title = await factory.scalar("SELECT title FROM book WHERE id = :b", b=book)
    editor = await factory.scalar(
        "SELECT u.display_name FROM book b JOIN app_user u ON u.id = b.updated_by "
        "WHERE b.id = :b", b=book,
    )  # fmt: skip
    return title, editor


async def test_entry_page_shows_every_book_field(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    s = await _setup(factory, alice)
    page = await member.get(f"/entries/{s['entry']}")
    assert page.status_code == 200
    for field in ("title", "author_name_0", "series_name", "series_number", "isbn_13",
                  "status", "finished_on", "times_read", "notes"):  # fmt: skip
        assert re.search(rf'<label for="{field}"', page.text), field
    assert 'value="Mortt"' in page.text
    assert "every family member" in page.text


async def test_change_the_title_and_notes_together(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    s = await _setup(factory, alice)
    saved = await member.post(
        f"/entries/{s['entry']}", data=_form(s, title="Mort", isbn_13="9780552131063",
                                             series_number="4.5", notes="New note"),
    )  # fmt: skip
    assert saved.status_code == 303, saved.text
    assert await _book(factory, s["book"]) == ("Mort", "Alice")
    assert await factory.scalar("SELECT isbn_13 FROM book") == "9780552131063"
    assert str(await factory.scalar("SELECT series_number FROM book")) == "4.50"
    assert await factory.scalar("SELECT notes FROM reading_entry") == "New note"
    shown = await member.get(saved.headers["location"])
    assert "<h1>Mort</h1>" in shown.text


async def test_change_the_author_and_series(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    s = await _setup(factory, alice)
    saved = await member.post(
        f"/entries/{s['entry']}",
        data=_form(s, author_name_0="Neil Gaiman", author_id_0="", author_name_1="Terry Pratchett",
                   author_id_1=str(s["author"]), series_name="", series_id="", series_number=""),
    )  # fmt: skip
    assert saved.status_code == 303, saved.text
    names = await factory.scalar(
        "SELECT array_agg(a.name ORDER BY ba.position) FROM book_author ba "
        "JOIN author a ON a.id = ba.author_id"
    )
    assert names == ["Neil Gaiman", "Terry Pratchett"]
    assert await factory.scalar("SELECT series_id FROM book") is None


async def test_reading_only_changes_leave_the_book_alone(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    s = await _setup(factory, alice)
    saved = await member.post(f"/entries/{s['entry']}", data=_form(s, notes="Just mine"))
    assert saved.status_code == 303, saved.text
    assert await _book(factory, s["book"]) == ("Mortt", "Ben")  # not marked as edited
    assert await factory.scalar("SELECT notes FROM reading_entry") == "Just mine"


async def test_a_bad_book_field_saves_nothing(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    s = await _setup(factory, alice)
    refused = await member.post(f"/entries/{s['entry']}", data=_form(s, title="", notes="X"))
    assert refused.status_code == 422
    assert "Enter a title" in refused.text
    assert ">X</textarea>" in refused.text  # what was typed is kept
    assert await factory.scalar("SELECT notes FROM reading_entry") == "Old note"
    assert await _book(factory, s["book"]) == ("Mortt", "Ben")


async def test_a_bad_reading_field_saves_nothing(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    s = await _setup(factory, alice)
    refused = await member.post(
        f"/entries/{s['entry']}", data=_form(s, title="Mort", times_read="many")
    )
    assert refused.status_code == 422
    assert "Enter a whole number from 0 to 99" in refused.text
    assert 'value="Mort"' in refused.text
    assert await _book(factory, s["book"]) == ("Mortt", "Ben")


async def test_a_taken_series_number_saves_nothing(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    s = await _setup(factory, alice)
    await factory.book("Sourcery", s["ben"], series_id=s["series"], series_number="5")
    refused = await member.post(
        f"/entries/{s['entry']}", data=_form(s, series_number="5", notes="Changed")
    )
    assert refused.status_code == 409
    assert "Another book already has this number in the series" in refused.text
    assert await factory.scalar("SELECT notes FROM reading_entry") == "Old note"


async def test_someone_elses_entry_is_not_found(
    factory: Factory, alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    s = await _setup(factory, alice)
    ben = await signed_in(client_factory(), s["ben"])
    sent = await ben.post(f"/entries/{s['entry']}", data=_form(s, title="Hijacked"))
    assert sent.status_code == 404
    assert await _book(factory, s["book"]) == ("Mortt", "Ben")
