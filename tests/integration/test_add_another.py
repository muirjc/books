"""Spec 004: "Add and add another" on Add a book (contracts/ui-add-another.md)."""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in, without_finished


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice", display_name="Alice")


@pytest.fixture
async def member(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


@pytest.fixture
async def dresden(factory: Factory, alice: TestUser) -> dict[str, uuid.UUID]:
    author = await factory.author("Jim Butcher", alice)
    series = await factory.series("The Dresden Files", alice)
    return {"author": author, "series": series}


def form(ids: dict[str, uuid.UUID], **overrides: str) -> dict[str, str]:
    data = {
        "title": "Grave Peril",
        "author_id_0": str(ids["author"]),
        "author_name_0": "Jim Butcher",
        "series_id": str(ids["series"]),
        "series_name": "The Dresden Files",
        "series_number": "3",
        "isbn_13": "9780451458445",
        "status": "finished",
        "finished_on": "2026-03-01",
        "summary": "A ghost story.",
        "notes": "Private note.",
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


async def entries(factory: Factory) -> int:
    return int(await factory.scalar("SELECT count(*) FROM reading_entry"))


def after_id(response: httpx.Response) -> str:
    # spec 017: a book added as Finished also carries finished=<book> (the favorite offer)
    location = response.headers["location"]
    match = re.fullmatch(r"/books/add\?after=([0-9a-f-]{36})(?:&finished=[0-9a-f-]{36})?", location)
    assert match, response.headers.get("location")
    return match.group(1)


def value(page: str, name: str) -> str:
    """The value of the input named ``name`` (or the selected option of a select)."""
    tag = re.search(rf'<input[^>]*\bname="{name}"[^>]*>', page)
    if tag:
        found = re.search(r'\bvalue="([^"]*)"', tag.group(0))
        return html.unescape(found.group(1)) if found else ""
    select = re.search(rf'<select[^>]*\bname="{name}"[^>]*>(.*?)</select>', page, re.S)
    if select:
        chosen = re.search(r'<option value="([^"]*)" selected', select.group(1))
        return chosen.group(1) if chosen else ""
    area = re.search(rf'<textarea[^>]*\bname="{name}"[^>]*>(.*?)</textarea>', page, re.S)
    assert area, name
    return html.unescape(area.group(1))


def hidden_then(page: str) -> str:
    found = re.findall(r'<input type="hidden" name="then" value="([a-z]+)">', page)
    assert found, "hidden then"
    assert len(set(found)) == 1, found
    return found[0]


# --------------------------------------------------------------------------- foundational


async def test_then_choice_last_value_wins(
    member: httpx.AsyncClient, dresden: dict[str, uuid.UUID]
) -> None:
    """The hidden field comes first and the clicked button later (research R2)."""
    cases: list[tuple[list[tuple[str, str]], bool]] = [
        ([("then", "another"), ("then", "list")], False),
        ([("then", "list"), ("then", "another")], True),
        ([("then", "something-else")], False),
    ]
    for n, (thens, another) in enumerate(cases):
        data = list(form(dresden, title=f"Book {n}", series_number="", isbn_13="").items())
        response = await member.post(
            "/books/add",
            content=httpx.QueryParams(data + thens).__str__(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 303, thens
        location = response.headers["location"]
        assert location.startswith("/books/add?after=") == another, (thens, location)


# --------------------------------------------------------------------------- US1


@pytest.mark.ac("004/AC-01")
async def test_add_and_add_another_redirects_to_fresh_form(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID]
) -> None:
    response = await member.post("/books/add", data=form(dresden, then="another"))
    assert response.status_code == 303
    entry = after_id(response)
    assert await entries(factory) == 1
    assert (
        await factory.scalar("SELECT b.title FROM reading_entry e JOIN book b ON b.id = e.book_id "
                             "WHERE e.id = :e", e=uuid.UUID(entry))
    ) == "Grave Peril"  # fmt: skip


@pytest.mark.ac("004/AC-02")
@pytest.mark.ac("004/AC-03")
async def test_confirmation_names_the_book(
    member: httpx.AsyncClient, dresden: dict[str, uuid.UUID]
) -> None:
    entry = after_id(await member.post("/books/add", data=form(dresden, then="another")))
    page = (await member.get(f"/books/add?after={entry}")).text
    notice = re.search(r'<p class="notice" role="status" id="added-notice">(.*?)</p>', page, re.S)
    assert notice, "confirmation"
    assert re.sub(r"<[^>]+>", "", html.unescape(notice.group(1))).strip() == (
        "Added “Grave Peril” to your list."
    )
    assert f'href="/entries/{entry}"' in notice.group(1)
    title = re.search(r'<input id="title"[^>]*>', page)
    assert title and " autofocus" in title.group(0)
    describedby = re.search(r'aria-describedby="([^"]*)"', title.group(0))
    assert describedby and "added-notice" in describedby.group(1).split()
    plain = (await member.get("/books/add")).text
    assert "added-notice" not in plain
    plain_title = re.search(r'<input id="title"[^>]*>', plain)
    assert plain_title and "autofocus" not in plain_title.group(0)


@pytest.mark.ac("004/AC-04")
async def test_add_to_my_list_unchanged(
    member: httpx.AsyncClient, dresden: dict[str, uuid.UUID]
) -> None:
    for n, then in enumerate(("list", None)):
        data = form(dresden, title=f"Book {n}", series_number="", isbn_13="")
        if then:
            data["then"] = then
        response = await member.post("/books/add", data=data)
        assert response.status_code == 303
        assert without_finished(response.headers["location"]) == "/?msg=added"


@pytest.mark.ac("004/AC-05")
async def test_reload_does_not_add_again(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID]
) -> None:
    entry = after_id(await member.post("/books/add", data=form(dresden, then="another")))
    for _ in range(2):
        assert (await member.get(f"/books/add?after={entry}")).status_code == 200
    assert await entries(factory) == 1


async def test_after_other_members_entry_is_a_plain_form(
    member: httpx.AsyncClient, factory: Factory, client_factory: Callable[[], httpx.AsyncClient]
) -> None:
    """FR-009, Principle I: only the member's own entry is carried over."""
    ben = await factory.user("ben", display_name="Ben")
    secret_author = await factory.author("Secret Author", ben)
    secret_series = await factory.series("Secret Series", ben)
    book = await factory.book(
        "Ben's Secret Book", ben, author_ids=[secret_author], series_id=secret_series,
        series_number="2",
    )  # fmt: skip
    bens_entry = await factory.entry(ben, book)
    gone = uuid.uuid4()
    plain = (await member.get("/books/add")).text
    for after in (str(bens_entry), str(gone), "not-a-uuid"):
        response = await member.get(f"/books/add?after={after}")
        assert response.status_code == 200, after
        page = response.text
        for secret in ("Ben's Secret Book", "Secret Author", "Secret Series", "added-notice"):
            assert secret not in html.unescape(page), (after, secret)
        assert value(page, "author_name_0") == value(plain, "author_name_0") == ""


# --------------------------------------------------------------------------- US2


@pytest.mark.ac("004/AC-07")
@pytest.mark.ac("004/AC-08")
@pytest.mark.ac("004/AC-09")
@pytest.mark.ac("004/AC-10")
async def test_next_form_carries_author_series_number_status(
    member: httpx.AsyncClient, dresden: dict[str, uuid.UUID]
) -> None:
    entry = after_id(
        await member.post("/books/add", data=form(dresden, then="another", status="reading"))
    )
    page = (await member.get(f"/books/add?after={entry}")).text
    assert value(page, "author_name_0") == "Jim Butcher"
    assert value(page, "author_id_0") == str(dresden["author"])
    assert value(page, "series_name") == "The Dresden Files"
    assert value(page, "series_id") == str(dresden["series"])
    assert value(page, "series_number") == "4"
    assert value(page, "status") == "reading"
    for empty in ("title", "book_id", "isbn_13", "finished_on", "summary", "notes"):
        assert value(page, empty) == "", empty
    assert hidden_then(page) == "another"


@pytest.mark.ac("004/AC-11")
async def test_carried_values_are_editable(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID]
) -> None:
    entry = after_id(await member.post("/books/add", data=form(dresden, then="another")))
    page = (await member.get(f"/books/add?after={entry}")).text
    carried = {
        k: value(page, k)
        for k in ("author_name_0", "author_id_0", "series_name", "series_id", "series_number",
                  "status")
    }  # fmt: skip
    authors_before = await factory.scalar("SELECT count(*) FROM author")
    series_before = await factory.scalar("SELECT count(*) FROM series")
    as_is = await member.post("/books/add", data=carried | {"title": "Summer Knight"})
    assert as_is.status_code == 303
    assert await factory.scalar("SELECT count(*) FROM author") == authors_before
    assert await factory.scalar("SELECT count(*) FROM series") == series_before
    assert (
        await factory.scalar("SELECT series_number FROM book WHERE title = 'Summer Knight'")
    ) == 4
    changed = await member.post(
        "/books/add",
        data=carried | {"title": "Side Jobs", "series_name": "", "series_id": "",
                        "series_number": "", "status": "want_to_read"},
    )  # fmt: skip
    assert changed.status_code == 303
    assert await factory.scalar("SELECT series_id FROM book WHERE title = 'Side Jobs'") is None
    assert (
        await factory.scalar("SELECT e.status FROM reading_entry e JOIN book b ON b.id = e.book_id"
                             " WHERE b.title = 'Side Jobs'")
    ) == "want_to_read"  # fmt: skip


@pytest.mark.ac("004/AC-12")
async def test_carry_over_from_picked_catalog_book(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, dresden: dict[str, uuid.UUID]
) -> None:
    ben = await factory.user("ben", display_name="Ben")
    book = await factory.book(
        "Dead Beat", ben, author_ids=[dresden["author"]], series_id=dresden["series"],
        series_number="7",
    )  # fmt: skip
    response = await member.post(
        "/books/add",
        data={"title": "Dead Beat", "book_id": str(book), "status": "want_to_read",
              "then": "another"},
    )  # fmt: skip
    page = (await member.get(f"/books/add?after={after_id(response)}")).text
    assert value(page, "author_id_0") == str(dresden["author"])
    assert value(page, "series_id") == str(dresden["series"])
    assert value(page, "series_number") == "8"
    assert value(page, "status") == "want_to_read"
    assert value(page, "book_id") == ""


@pytest.mark.ac("004/AC-13")
async def test_suggested_number_taken_shows_usual_conflict(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, dresden: dict[str, uuid.UUID]
) -> None:
    held = await factory.book(
        "Summer Knight", alice, author_ids=[dresden["author"]], series_id=dresden["series"],
        series_number="4",
    )  # fmt: skip
    entry = after_id(await member.post("/books/add", data=form(dresden, then="another")))
    page = (await member.get(f"/books/add?after={entry}")).text
    assert value(page, "series_number") == "4"
    before = await entries(factory)
    taken = await member.post(
        "/books/add",
        data={"title": "Death Masks", "author_id_0": str(dresden["author"]),
              "author_name_0": "Jim Butcher", "series_id": str(dresden["series"]),
              "series_name": "The Dresden Files", "series_number": "4", "status": "finished",
              "then": "another"},
    )  # fmt: skip
    assert taken.status_code == 409
    assert "Another book already has this number in the series" in html.unescape(taken.text)
    assert f'href="/catalog/books/{held}/edit"' in taken.text
    assert await entries(factory) == before


async def test_carry_over_shows_current_names(
    member: httpx.AsyncClient, factory: Factory, dresden: dict[str, uuid.UUID]
) -> None:
    entry = after_id(await member.post("/books/add", data=form(dresden, then="another")))
    await factory.execute("UPDATE author SET name = 'James Butcher' WHERE id = :a",
                          a=dresden["author"])  # fmt: skip
    await factory.execute("UPDATE series SET name = 'Dresden Files' WHERE id = :s",
                          s=dresden["series"])  # fmt: skip
    page = (await member.get(f"/books/add?after={entry}")).text
    assert value(page, "author_name_0") == "James Butcher"
    assert value(page, "series_name") == "Dresden Files"


# --------------------------------------------------------------------------- US3


async def _conflict_cases(
    factory: Factory, alice: TestUser, ids: dict[str, uuid.UUID]
) -> dict[str, tuple[dict[str, str], int, str]]:
    other = await factory.book(
        "Storm Front", alice, author_ids=[ids["author"]], series_id=ids["series"],
        series_number="1", isbn_13="9780451457813",
    )  # fmt: skip
    await factory.entry(alice, other)
    await factory.book("Restoration of Faith", alice, author_ids=[ids["author"]],
                       isbn_13="9780451457998")  # fmt: skip
    base = form(ids, series_number="", isbn_13="")
    return {
        "missing title": (base | {"title": ""}, 422, "Enter a title"),
        "author exists": (
            base | {"author_id_0": "", "author_name_0": "jim butcher"}, 409,
            "Use existing author",
        ),
        "series exists": (
            base | {"series_id": "", "series_name": "the dresden files"}, 409,
            "Use existing series",
        ),
        "isbn exists": (
            base | {"isbn_13": "9780451457998"}, 409, "A book with this ISBN is already",
        ),
        "number taken": (
            base | {"series_number": "1"}, 409,
            "Another book already has this number in the series",
        ),
        "already on list": (
            {"title": "Storm Front", "book_id": str(other), "status": "finished"}, 409,
            "Already on your list",
        ),
    }  # fmt: skip


@pytest.mark.ac("004/AC-14")
@pytest.mark.ac("004/AC-16")
async def test_errors_and_conflicts_same_for_both_buttons(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, dresden: dict[str, uuid.UUID]
) -> None:
    cases = await _conflict_cases(factory, alice, dresden)
    before = await entries(factory)
    for name, (data, status, message) in cases.items():
        pages = {}
        for then in ("list", "another"):
            response = await member.post("/books/add", data=data | {"then": then})
            assert response.status_code == status, (name, then)
            assert message in html.unescape(response.text), (name, then)
            assert hidden_then(response.text) == then, (name, then)
            pages[then] = re.sub(r'(name="then" value=")[a-z]+', r"\1", response.text)
        assert pages["list"] == pages["another"], name
    assert await entries(factory) == before


@pytest.mark.ac("004/AC-15")
async def test_conflict_choice_keeps_add_another(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, dresden: dict[str, uuid.UUID]
) -> None:
    cases = await _conflict_cases(factory, alice, dresden)
    author_case = cases["author exists"][0] | {"then": "another"}
    page = (await member.post("/books/add", data=author_case)).text
    button = re.search(r'<button type="submit" name="author_id_0" value="([^"]+)">', page)
    assert button, "use existing author button"
    # As the browser sends it: hidden then=another, then the clicked button's own field.
    chosen = author_case | {"author_id_0": button.group(1)}
    response = await member.post("/books/add", data=chosen)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/books/add?after=")

    isbn_case = cases["isbn exists"][0] | {"then": "another"}
    page = (await member.post("/books/add", data=isbn_case)).text
    isbn_form = re.search(r'<form method="post" action="/books/add" class="inline-form">(.*?)'
                          r"</form>", page, re.S)  # fmt: skip
    assert isbn_form, "ISBN conflict form"
    assert '<input type="hidden" name="then" value="another">' in isbn_form.group(1)
    instead = re.search(r'name="book_id" value="([^"]+)"', isbn_form.group(1))
    assert instead
    fields: dict[str, Any] = dict(
        re.findall(r'<input type="hidden" name="([a-z_]+)" value="([^"]*)">', isbn_form.group(1))
    )
    response = await member.post("/books/add", data=fields | {"book_id": instead.group(1)})
    assert response.status_code == 303
    assert response.headers["location"].startswith("/books/add?after=")

    # Hidden then=another, but the Add to my list button clicked: My books.
    response = await member.post(
        "/books/add",
        content=httpx.QueryParams(
            list((cases["author exists"][0] | {"author_id_0": button.group(1),
                                               "title": "Fool Moon"}).items())
            + [("then", "another"), ("then", "list")]
        ).__str__(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )  # fmt: skip
    assert response.status_code == 303
    assert without_finished(response.headers["location"]) == "/?msg=added"
