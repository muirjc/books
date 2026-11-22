"""books-mbx: a book page opened before another member changed the book never writes the
old values back. Each book field the member left as shown keeps the book's current value;
fields they changed are saved (the spec 007 release-date rule, for every book field)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from datetime import date

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice", display_name="Alice")


@pytest.fixture
async def ben(factory: Factory) -> TestUser:
    return await factory.user("ben", display_name="Ben")


@pytest.fixture
async def member(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


@pytest.fixture
async def other(
    ben: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), ben)


@pytest.fixture
async def book(factory: Factory, alice: TestUser, ben: TestUser) -> dict[str, uuid.UUID]:
    pratchett = await factory.author("Terry Pratchett", alice)
    gaiman = await factory.author("Neil Gaiman", alice)
    discworld = await factory.series("Discworld", alice)
    other_series = await factory.series("Witches", alice)
    mort = await factory.book(
        "Mort", alice, author_ids=[pratchett], series_id=discworld, series_number="4",
        isbn_13="9780552131063", release_date=date(1987, 11, 12),
    )  # fmt: skip
    entry = await factory.entry(alice, mort, notes="first")
    return {
        "pratchett": pratchett, "gaiman": gaiman, "discworld": discworld,
        "witches": other_series, "mort": mort, "entry": entry,
    }  # fmt: skip


def page_form(page: httpx.Response) -> dict[str, str]:
    """The page's book form inputs as the browser would send them, unchanged (text inputs,
    hidden fields, the selected status, textareas). The header's sign-out form is skipped."""
    match = re.search(
        r'<form method="post" action="/(?:entries|catalog/books)/[^"]+"[^>]*>(.*?)</form>',
        page.text,
        re.S,
    )
    assert match, "no book form on the page"
    form = match.group(1)
    data: dict[str, str] = {}
    for tag in re.findall(r"<input\b[^>]*>", form):
        name = re.search(r'name="([^"]+)"', tag)
        if not name or 'type="checkbox"' in tag or 'type="submit"' in tag:
            continue
        value = re.search(r'value="([^"]*)"', tag)
        data[name.group(1)] = value.group(1) if value else ""
    for name, body in re.findall(r'<textarea[^>]*name="([^"]+)"[^>]*>(.*?)</textarea>', form, re.S):
        data[name] = body
    selected = re.search(r'<option value="([^"]+)" selected>', form)
    if selected:
        data["status"] = selected.group(1)
    return {k: v.replace("&#39;", "'").replace("&amp;", "&") for k, v in data.items()}


async def current(factory: Factory, book_id: uuid.UUID) -> dict[str, object]:
    row = {
        key: await factory.scalar(f"SELECT {key} FROM book WHERE id = :id", id=book_id)
        for key in ("title", "series_id", "series_number", "isbn_13", "release_date")
    }
    row["authors"] = await factory.scalar(
        "SELECT string_agg(a.name, ', ' ORDER BY ba.position) FROM book_author ba "
        "JOIN author a ON a.id = ba.author_id WHERE ba.book_id = :id",
        id=book_id,
    )
    return row


async def ben_changes_everything(other: httpx.AsyncClient, book: dict[str, uuid.UUID]) -> None:
    edit = f"/catalog/books/{book['mort']}/edit"
    data = page_form(await other.get(edit))
    data.update(
        {
            "title": "Mort (revised)",
            "author_name_0": "Neil Gaiman", "author_id_0": str(book["gaiman"]),
            "series_name": "Witches", "series_id": str(book["witches"]),
            "series_number": "9", "isbn_13": "9780061020681", "release_date": "1988-01-01",
        }
    )  # fmt: skip
    saved = await other.post(edit, data=data)
    assert saved.status_code == 303, saved.text


BEN = {
    "title": "Mort (revised)", "authors": "Neil Gaiman", "isbn_13": "9780061020681",
    "release_date": date(1988, 1, 1),
}  # fmt: skip


async def test_stale_entry_page_keeps_others_edits(
    member: httpx.AsyncClient,
    other: httpx.AsyncClient,
    factory: Factory,
    book: dict[str, uuid.UUID],
) -> None:
    """Alice opened her entry page, Ben then changed every book field; Alice saves only her
    notes. Every one of Ben's changes stays."""
    url = f"/entries/{book['entry']}"
    stale = page_form(await member.get(url))
    await ben_changes_everything(other, book)
    stale["notes"] = "only my notes"
    saved = await member.post(url, data=stale)
    assert saved.status_code == 303, saved.text
    now = await current(factory, book["mort"])
    for key, value in BEN.items():
        assert now[key] == value, key
    assert now["series_id"] == book["witches"]
    assert str(now["series_number"]) == "9.00"
    assert (
        await factory.scalar("SELECT notes FROM reading_entry WHERE id = :id", id=book["entry"])
        == "only my notes"
    )
    # Nothing of the book changed for Alice, so Ben stays its last editor.
    editor = await factory.scalar(
        "SELECT u.login FROM book b JOIN app_user u ON u.id = b.updated_by WHERE b.id = :id",
        id=book["mort"],
    )
    assert editor == "ben"


async def test_stale_edit_page_keeps_others_edits(
    member: httpx.AsyncClient,
    other: httpx.AsyncClient,
    factory: Factory,
    book: dict[str, uuid.UUID],
) -> None:
    edit = f"/catalog/books/{book['mort']}/edit"
    stale = page_form(await member.get(edit))
    await ben_changes_everything(other, book)
    assert (await member.post(edit, data=stale)).status_code == 303
    now = await current(factory, book["mort"])
    for key, value in BEN.items():
        assert now[key] == value, key


async def test_changed_fields_still_save(
    member: httpx.AsyncClient,
    other: httpx.AsyncClient,
    factory: Factory,
    book: dict[str, uuid.UUID],
) -> None:
    """Alice changes the title and clears the ISBN on her stale page; Ben's other changes
    stay, and hers are saved."""
    edit = f"/catalog/books/{book['mort']}/edit"
    stale = page_form(await member.get(edit))
    await ben_changes_everything(other, book)
    stale.update({"title": "Mort: A Discworld Novel", "isbn_13": ""})
    assert (await member.post(edit, data=stale)).status_code == 303
    now = await current(factory, book["mort"])
    assert now["title"] == "Mort: A Discworld Novel"
    assert now["isbn_13"] is None
    assert now["authors"] == "Neil Gaiman"
    assert now["series_id"] == book["witches"]
    assert now["release_date"] == date(1988, 1, 1)


async def test_unchanged_page_saves_as_before(
    member: httpx.AsyncClient, factory: Factory, book: dict[str, uuid.UUID]
) -> None:
    """With nobody else editing, a page saved as shown changes nothing, and a field changed
    on it is saved; a form without the remembered values behaves as before."""
    edit = f"/catalog/books/{book['mort']}/edit"
    shown = page_form(await member.get(edit))
    for name in ("title_was", "authors_was", "series_id_was", "series_number_was",
                 "isbn_13_was", "release_date_was"):  # fmt: skip
        assert name in shown, name
    assert shown["authors_was"] == str(book["pratchett"])
    assert (await member.post(edit, data=shown)).status_code == 303
    assert (await current(factory, book["mort"]))["title"] == "Mort"
    plain = {k: v for k, v in shown.items() if not k.endswith("_was")}
    plain["title"] = "Mort!"
    assert (await member.post(edit, data=plain)).status_code == 303
    assert (await current(factory, book["mort"]))["title"] == "Mort!"


async def test_remembered_values_survive_an_error_page(
    member: httpx.AsyncClient,
    other: httpx.AsyncClient,
    factory: Factory,
    book: dict[str, uuid.UUID],
) -> None:
    """A refused save shows the page again with the values first shown, not the ones
    typed, so fixing the error and saving still keeps Ben's edits."""
    edit = f"/catalog/books/{book['mort']}/edit"
    stale = page_form(await member.get(edit))
    await ben_changes_everything(other, book)
    refused = await member.post(edit, data={**stale, "isbn_13": "123"})
    assert refused.status_code == 422
    again = page_form(refused)
    assert again["isbn_13_was"] == "9780552131063"
    assert again["title_was"] == "Mort"
    again["isbn_13"] = "9780552131063"  # put it back as shown
    assert (await member.post(edit, data=again)).status_code == 303
    now = await current(factory, book["mort"])
    for key, value in BEN.items():
        assert now[key] == value, key
