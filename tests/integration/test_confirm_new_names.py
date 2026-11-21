"""Spec 005: a typed author or series not in the catalog needs confirming (books-ca5).

Contract: specs/005-confirm-new-names/contracts/ui-new-names.md.
"""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from book_tracker.services import catalog as catalog_service
from tests.conftest import Factory, TestUser, signed_in

PROMPT = "“{}” is not in the family catalog yet"


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice", display_name="Alice")


@pytest.fixture
async def member(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


@pytest.fixture
async def robb(factory: Factory, alice: TestUser) -> dict[str, uuid.UUID]:
    return {
        "robb": await factory.author(
            "J.D. Robb", alice, is_pen_name=True, real_name="Nora Roberts"
        ),
        "in_death": await factory.series("In Death", alice),
        "butcher": await factory.author("Jim Butcher", alice),
        "dresden": await factory.series("The Dresden Files", alice),
    }


async def counts(factory: Factory) -> tuple[int, ...]:
    found = []
    for table in ("author", "series", "book", "reading_entry"):
        found.append(int(await factory.scalar(f"SELECT count(*) FROM {table}")))
    return tuple(found)


def text_of(page: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", page))


def field_error(page: str, field: str) -> str:
    found = re.search(rf'<p class="field-error" id="{field}-error">(.*?)</p>', page, re.S)
    return html.unescape(found.group(1)).strip() if found else ""


def summary_links(page: str) -> list[tuple[str, str]]:
    box = re.search(r'<div class="error-summary".*?</div>', page, re.S)
    if not box:
        return []
    return [
        (href, html.unescape(t))
        for href, t in re.findall(r'<a href="#([a-z_0-9]+)">(.*?)</a>', box.group(0))
    ]


def use_buttons(page: str, name: str) -> list[tuple[str, str]]:
    return [
        (value, html.unescape(label))
        for value, label in re.findall(
            rf'<button type="submit" name="{name}" value="([^"]+)">Use “(.*?)”</button>', page
        )
    ]


def confirm_button(page: str, name: str) -> str | None:
    found = re.search(rf'<button type="submit" name="{name}" value="([^"]*)">Add “', page)
    return html.unescape(found.group(1)) if found else None


def add_form(**fields: str) -> dict[str, str]:
    data = {"title": "Naked in Death", "author_name_0": "J DM Robb", "status": "finished"}
    data.update(fields)
    return {k: v for k, v in data.items() if v is not None}


async def book_authors(factory: Factory, title: str) -> list[str]:
    rows = await factory.scalar(
        "SELECT string_agg(a.name, '|' ORDER BY ba.position) FROM book b "
        "JOIN book_author ba ON ba.book_id = b.id JOIN author a ON a.id = ba.author_id "
        "WHERE b.title = :t", t=title,
    )  # fmt: skip
    return str(rows).split("|") if rows else []


# --------------------------------------------------------------------------- foundational


async def test_similar_authors_and_series_from_catalog(
    app: Any, robb: dict[str, uuid.UUID]
) -> None:
    async with app.state.db.sessionmaker() as db:
        found = await catalog_service.similar_authors(db, "J DM Robb")
        assert found[0] == (robb["robb"], "J.D. Robb")
        assert (robb["robb"], "J.D. Robb") in await catalog_service.similar_authors(
            db, "Nora Roberts"
        )
        series = await catalog_service.similar_series(db, "Dresdin Files")
        assert series[0] == (robb["dresden"], "The Dresden Files")
        assert await catalog_service.similar_authors(db, "Ann Leckie") == []


# --------------------------------------------------------------------------- US1


@pytest.mark.ac("005/AC-01")
async def test_new_author_prompts_and_saves_nothing(
    member: httpx.AsyncClient, factory: Factory, robb: dict[str, uuid.UUID]
) -> None:
    before = await counts(factory)
    page = await member.post("/books/add", data=add_form(notes="Kept note"))
    assert page.status_code == 409
    assert await counts(factory) == before
    message = PROMPT.format("J DM Robb")
    assert field_error(page.text, "author_name_0") == message
    assert ("author_name_0", message) in summary_links(page.text)
    assert 'value="Naked in Death"' in page.text and "Kept note" in page.text


@pytest.mark.ac("005/AC-02")
async def test_use_similar_author(
    member: httpx.AsyncClient, factory: Factory, robb: dict[str, uuid.UUID]
) -> None:
    page = (await member.post("/books/add", data=add_form())).text
    offered = use_buttons(page, "use_author_0")
    assert offered[0] == (str(robb["robb"]), "J.D. Robb") and len(offered) <= 3
    authors = await factory.scalar("SELECT count(*) FROM author")
    for junk in (str(uuid.uuid4()), "not-an-id"):
        again = await member.post("/books/add", data=add_form(use_author_0=junk))
        assert again.status_code == 409, junk
        assert field_error(again.text, "author_name_0") == PROMPT.format("J DM Robb")
    saved = await member.post("/books/add", data=add_form(use_author_0=str(robb["robb"])))
    assert saved.status_code == 303
    assert await book_authors(factory, "Naked in Death") == ["J.D. Robb"]
    assert await factory.scalar("SELECT count(*) FROM author") == authors


@pytest.mark.ac("005/AC-03")
async def test_confirm_new_author(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, robb: dict[str, uuid.UUID]
) -> None:
    page = (await member.post("/books/add", data=add_form())).text
    assert confirm_button(page, "confirm_author_0") == "J DM Robb"
    saved = await member.post("/books/add", data=add_form(confirm_author_0="J DM Robb"))
    assert saved.status_code == 303
    assert await book_authors(factory, "Naked in Death") == ["J DM Robb"]
    # Someone else adds the exact name between the prompt and the confirmation.
    await factory.author("Ann Leckie", alice)
    clash = await member.post(
        "/books/add",
        data=add_form(title="Ancillary Justice", author_name_0="Ann Leckie",
                      confirm_author_0="Ann Leckie"),
    )  # fmt: skip
    assert clash.status_code == 409
    assert "Use existing author" in clash.text
    assert await factory.scalar("SELECT count(*) FROM author WHERE name = 'Ann Leckie'") == 1


@pytest.mark.ac("005/AC-04")
async def test_new_series_prompt_use_and_confirm(
    member: httpx.AsyncClient, factory: Factory, robb: dict[str, uuid.UUID]
) -> None:
    base = add_form(
        author_name_0="Jim Butcher", author_id_0=str(robb["butcher"]), title="Storm Front",
        series_name="Dresdin Files", series_number="1",
    )  # fmt: skip
    page = await member.post("/books/add", data=base)
    assert page.status_code == 409
    assert field_error(page.text, "series_name") == PROMPT.format("Dresdin Files")
    assert use_buttons(page.text, "use_series")[0] == (str(robb["dresden"]), "The Dresden Files")
    assert confirm_button(page.text, "confirm_series") == "Dresdin Files"
    used = await member.post("/books/add", data=base | {"use_series": str(robb["dresden"])})
    assert used.status_code == 303
    assert (await factory.scalar("SELECT series_id FROM book WHERE title = 'Storm Front'")) == robb[
        "dresden"
    ]
    confirmed = await member.post(
        "/books/add",
        data=base | {"title": "Fool Moon", "confirm_series": "Dresdin Files"},
    )
    assert confirmed.status_code == 303
    assert await factory.scalar("SELECT count(*) FROM series WHERE name = 'Dresdin Files'") == 1


@pytest.mark.ac("005/AC-05")
async def test_several_new_names_on_one_page(
    member: httpx.AsyncClient, factory: Factory, robb: dict[str, uuid.UUID]
) -> None:
    data = add_form(title="Good Omens", author_name_0="Niel Gaiman",
                    author_name_1="Terry Pratchet", series_name="Omens")  # fmt: skip
    before = await counts(factory)
    page = await member.post("/books/add", data=data)
    assert page.status_code == 409
    assert await counts(factory) == before
    for field, name in (("author_name_0", "Niel Gaiman"), ("author_name_1", "Terry Pratchet"),
                        ("series_name", "Omens")):  # fmt: skip
        assert field_error(page.text, field) == PROMPT.format(name), field
    one = await member.post("/books/add", data=data | {"confirm_author_0": "Niel Gaiman"})
    assert one.status_code == 409
    assert '<input type="hidden" name="confirm_author_0" value="Niel Gaiman">' in one.text
    assert field_error(one.text, "author_name_0") == ""
    assert field_error(one.text, "author_name_1") == PROMPT.format("Terry Pratchet")
    assert await counts(factory) == before
    done = await member.post(
        "/books/add",
        data=data | {"confirm_author_0": "Niel Gaiman", "confirm_author_1": "Terry Pratchet",
                     "confirm_series": "Omens"},
    )  # fmt: skip
    assert done.status_code == 303
    assert await book_authors(factory, "Good Omens") == ["Niel Gaiman", "Terry Pratchet"]


@pytest.mark.ac("005/AC-06")
async def test_confirmation_is_for_the_exact_name(
    member: httpx.AsyncClient, factory: Factory, robb: dict[str, uuid.UUID]
) -> None:
    before = await counts(factory)
    page = await member.post(
        "/books/add", data=add_form(author_name_0="J D M Robb", confirm_author_0="J DM Robb")
    )
    assert page.status_code == 409
    assert field_error(page.text, "author_name_0") == PROMPT.format("J D M Robb")
    assert await counts(factory) == before
    spaced = await member.post(
        "/books/add", data=add_form(author_name_0=" J  DM Robb ", confirm_author_0="J DM Robb")
    )
    assert spaced.status_code == 303  # the same name once spacing is tidied


@pytest.mark.ac("005/AC-07")
async def test_picked_and_exact_names_unchanged(
    member: httpx.AsyncClient, factory: Factory, robb: dict[str, uuid.UUID]
) -> None:
    picked = await member.post(
        "/books/add",
        data=add_form(author_name_0="J.D. Robb", author_id_0=str(robb["robb"]),
                      series_name="In Death", series_id=str(robb["in_death"])),
    )  # fmt: skip
    assert picked.status_code == 303
    exact = await member.post(
        "/books/add", data=add_form(title="Glory in Death", author_name_0="j.d. robb")
    )
    assert exact.status_code == 409
    assert "Use existing author" in exact.text
    assert field_error(exact.text, "author_name_0") != PROMPT.format("j.d. robb")


# --------------------------------------------------------------------------- US2


async def _entry_setup(
    factory: Factory, alice: TestUser, ids: dict[str, uuid.UUID]
) -> dict[str, Any]:
    book = await factory.book("Storm Front", alice, author_ids=[ids["butcher"]],
                              series_id=ids["dresden"], series_number="1")  # fmt: skip
    entry = await factory.entry(alice, book, notes="Old note")
    return {"book": book, "entry": entry}


def _book_form(ids: dict[str, uuid.UUID], **overrides: str) -> dict[str, str]:
    data = {
        "title": "Storm Front", "author_name_0": "Jim Butcher", "author_id_0": str(ids["butcher"]),
        "series_name": "The Dresden Files", "series_id": str(ids["dresden"]),
        "series_number": "1", "isbn_13": "", "status": "finished", "finished_on": "",
        "times_read": "1", "notes": "Old note",
    }  # fmt: skip
    data.update(overrides)
    return data


@pytest.mark.ac("005/AC-08")
async def test_book_page_new_author_waits_for_confirmation(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, robb: dict[str, uuid.UUID]
) -> None:
    s = await _entry_setup(factory, alice, robb)
    data = _book_form(robb, author_name_0="Jim Bucher", author_id_0="", notes="New note")
    page = await member.post(f"/entries/{s['entry']}", data=data)
    assert page.status_code == 409
    assert field_error(page.text, "author_name_0") == PROMPT.format("Jim Bucher")
    assert use_buttons(page.text, "use_author_0")[0] == (str(robb["butcher"]), "Jim Butcher")
    assert await book_authors(factory, "Storm Front") == ["Jim Butcher"]
    assert await factory.scalar("SELECT notes FROM reading_entry WHERE id = :e",
                                e=s["entry"]) == "Old note"  # fmt: skip
    saved = await member.post(
        f"/entries/{s['entry']}", data=data | {"confirm_author_0": "Jim Bucher"}
    )
    assert saved.status_code == 303
    assert await book_authors(factory, "Storm Front") == ["Jim Bucher"]
    assert await factory.scalar("SELECT notes FROM reading_entry WHERE id = :e",
                                e=s["entry"]) == "New note"  # fmt: skip


@pytest.mark.ac("005/AC-09")
async def test_edit_book_new_series_prompt(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, robb: dict[str, uuid.UUID]
) -> None:
    s = await _entry_setup(factory, alice, robb)
    data = _book_form(robb, series_name="Dresdin Files", series_id="")
    path = f"/catalog/books/{s['book']}/edit"
    page = await member.post(path, data=data)
    assert page.status_code == 409
    assert field_error(page.text, "series_name") == PROMPT.format("Dresdin Files")
    used = await member.post(path, data=data | {"use_series": str(robb["dresden"])})
    assert used.status_code == 303
    confirmed = await member.post(path, data=data | {"confirm_series": "Dresdin Files"})
    assert confirmed.status_code == 303
    assert (
        await factory.scalar("SELECT s.name FROM book b JOIN series s ON s.id = b.series_id "
                             "WHERE b.id = :b", b=s["book"])
    ) == "Dresdin Files"  # fmt: skip


@pytest.mark.ac("005/AC-10")
async def test_unchanged_names_no_prompt(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, robb: dict[str, uuid.UUID]
) -> None:
    s = await _entry_setup(factory, alice, robb)
    entry = await member.post(f"/entries/{s['entry']}", data=_book_form(robb, notes="Changed"))
    assert entry.status_code == 303
    edit = await member.post(
        f"/catalog/books/{s['book']}/edit", data=_book_form(robb, title="Storm Front!")
    )
    assert edit.status_code == 303


# --------------------------------------------------------------------------- US3


@pytest.mark.ac("005/AC-11")
async def test_prompt_with_field_errors(
    member: httpx.AsyncClient, factory: Factory, robb: dict[str, uuid.UUID]
) -> None:
    before = await counts(factory)
    page = await member.post("/books/add", data=add_form(title="", isbn_13="123"))
    assert page.status_code == 422
    assert "Enter a title" in page.text
    assert field_error(page.text, "isbn_13")
    assert field_error(page.text, "author_name_0") == PROMPT.format("J DM Robb")
    assert use_buttons(page.text, "use_author_0")
    assert await counts(factory) == before


@pytest.mark.ac("005/AC-12")
async def test_add_another_keeps_choice_and_carries_new_author(
    member: httpx.AsyncClient, factory: Factory, robb: dict[str, uuid.UUID]
) -> None:
    page = await member.post("/books/add", data=add_form(then="another"))
    assert page.status_code == 409
    assert '<input type="hidden" name="then" value="another">' in page.text
    saved = await member.post(
        "/books/add", data=add_form(then="another", confirm_author_0="J DM Robb")
    )
    assert saved.status_code == 303
    assert saved.headers["location"].startswith("/books/add?after=")
    nxt = (await member.get(saved.headers["location"])).text
    new_id = await factory.scalar("SELECT id FROM author WHERE name = 'J DM Robb'")
    assert f'name="author_id_0" value="{new_id}"' in nxt
    again = await member.post(
        "/books/add",
        data={"title": "Glory in Death", "author_name_0": "J DM Robb",
              "author_id_0": str(new_id), "status": "finished"},
    )  # fmt: skip
    assert again.status_code == 303
