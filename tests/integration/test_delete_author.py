"""Spec 008: find authors with no books and delete them; authors with books can't be."""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable

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


@pytest.fixture
async def authors(factory: Factory, alice: TestUser) -> dict[str, uuid.UUID]:
    """J.D. Robb with two books; J DM Robb and Nobody Writes with none."""
    robb = await factory.author("J.D. Robb", alice)
    ids = {
        "robb": robb,
        "typo": await factory.author("J DM Robb", alice),
        "nobody": await factory.author("Nobody Writes", alice),
    }
    ids["naked"] = await factory.book("Naked in Death", alice, author_ids=[robb])
    ids["glory"] = await factory.book("Glory in Death", alice, author_ids=[robb])
    return ids


def text(page: httpx.Response) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", page.text)).split())


async def exists(factory: Factory, author_id: uuid.UUID) -> bool:
    return bool(await factory.scalar("SELECT count(*) FROM author WHERE id = :id", id=author_id))


# --------------------------------------------------------------------------- US1


@pytest.mark.ac("008/AC-01")
async def test_my_books_links_unused_authors(
    member: httpx.AsyncClient, factory: Factory, authors: dict[str, uuid.UUID]
) -> None:
    page = await member.get("/")
    assert '<a href="/catalog/authors/unused">Authors with no books (2)</a>' in page.text
    partial = await member.get("/", headers={"HX-Request": "true"})
    assert "/catalog/authors/unused" not in partial.text
    await factory.execute(
        "DELETE FROM author WHERE id IN (:a, :b)", a=authors["typo"], b=authors["nobody"]
    )
    assert "/catalog/authors/unused" not in (await member.get("/")).text


@pytest.mark.ac("008/AC-02")
async def test_unused_authors_page(
    member: httpx.AsyncClient, factory: Factory, authors: dict[str, uuid.UUID]
) -> None:
    page = await member.get("/catalog/authors/unused")
    assert page.status_code == 200
    assert "<h1>Authors with no books</h1>" in page.text
    links = re.findall(r'<a href="/catalog/authors/([0-9a-f-]{36})/edit">([^<]+)</a>', page.text)
    assert links == [(str(authors["typo"]), "J DM Robb"), (str(authors["nobody"]), "Nobody Writes")]
    assert "J.D. Robb" not in page.text
    await factory.execute(
        "DELETE FROM author WHERE id IN (:a, :b)", a=authors["typo"], b=authors["nobody"]
    )
    empty = await member.get("/catalog/authors/unused")
    assert "Every author in the family catalog has at least one book." in text(empty)


@pytest.mark.ac("008/AC-03")
async def test_delete_asks_first(
    member: httpx.AsyncClient, factory: Factory, authors: dict[str, uuid.UUID]
) -> None:
    edit = await member.get(f"/catalog/authors/{authors['typo']}/edit")
    assert "No book in the family catalog lists this author." in text(edit)
    assert f'action="/catalog/authors/{authors["typo"]}/delete"' in edit.text
    asked = await member.post(f"/catalog/authors/{authors['typo']}/delete", data={})
    assert asked.status_code == 200
    assert "Delete “J DM Robb” from the family catalog?" in text(asked)
    assert 'name="confirm" value="yes"' in asked.text
    assert await exists(factory, authors["typo"])


@pytest.mark.ac("008/AC-04")
async def test_delete_author(
    member: httpx.AsyncClient, factory: Factory, authors: dict[str, uuid.UUID]
) -> None:
    done = await member.post(f"/catalog/authors/{authors['typo']}/delete", data={"confirm": "yes"})
    assert done.status_code == 303
    assert done.headers["location"] == "/catalog/authors/unused?msg=deleted&author=J+DM+Robb"
    assert not await exists(factory, authors["typo"])
    page = await member.get(done.headers["location"])
    assert re.search(r'role="status"[^>]*>\s*Deleted “J DM Robb”\.', page.text)
    assert "J DM Robb</a>" not in page.text
    found = await member.get("/api/v1/authors", params={"q": "Robb"})
    assert [a["name"] for a in found.json()] == ["J.D. Robb"]
    assert (await member.get(f"/catalog/authors/{authors['typo']}/edit")).status_code == 404
    # The name in the message is text only.
    sneaky = await member.get("/catalog/authors/unused?msg=deleted&author=<b>x</b>")
    assert "<b>x</b>" not in sneaky.text and "&lt;b&gt;x&lt;/b&gt;" in sneaky.text


@pytest.mark.ac("008/AC-05")
async def test_cancel(member: httpx.AsyncClient, authors: dict[str, uuid.UUID]) -> None:
    asked = await member.post(f"/catalog/authors/{authors['typo']}/delete", data={})
    assert f'<a href="/catalog/authors/{authors["typo"]}/edit">Cancel</a>' in asked.text


# --------------------------------------------------------------------------- US2


@pytest.mark.ac("008/AC-06")
async def test_author_with_books_lists_them(
    member: httpx.AsyncClient, authors: dict[str, uuid.UUID]
) -> None:
    edit = await member.get(f"/catalog/authors/{authors['robb']}/edit")
    assert f'<a href="/catalog/books/{authors["glory"]}/edit">Glory in Death</a>' in edit.text
    assert f'<a href="/catalog/books/{authors["naked"]}/edit">Naked in Death</a>' in edit.text
    assert edit.text.index("Glory in Death") < edit.text.index("Naked in Death")
    assert (
        "This author can't be deleted while books list them. Change those books' authors first."
        in text(edit)
    )
    assert "/delete" not in edit.text


@pytest.mark.ac("008/AC-07")
async def test_book_added_meanwhile(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, authors: dict[str, uuid.UUID]
) -> None:
    asked = await member.post(f"/catalog/authors/{authors['typo']}/delete", data={})
    assert asked.status_code == 200
    await factory.book("Typo Book", alice, author_ids=[authors["typo"]])  # someone else, meanwhile
    refused = await member.post(
        f"/catalog/authors/{authors['typo']}/delete", data={"confirm": "yes"}
    )
    assert refused.status_code == 409
    assert "“J DM Robb” now has a book, so it wasn't deleted." in text(refused)
    assert "Typo Book" in refused.text
    assert await exists(factory, authors["typo"])


@pytest.mark.ac("008/AC-08")
async def test_delete_unknown_author(
    member: httpx.AsyncClient, authors: dict[str, uuid.UUID]
) -> None:
    gone = await member.post(f"/catalog/authors/{uuid.uuid4()}/delete", data={"confirm": "yes"})
    assert gone.status_code == 404
    first = await member.post(f"/catalog/authors/{authors['typo']}/delete", data={"confirm": "yes"})
    assert first.status_code == 303
    again = await member.post(f"/catalog/authors/{authors['typo']}/delete", data={"confirm": "yes"})
    assert again.status_code == 404


async def test_signed_out_cannot_delete(
    client_factory: Callable[[], httpx.AsyncClient],
    factory: Factory,
    authors: dict[str, uuid.UUID],
) -> None:
    anonymous = client_factory()
    response = await anonymous.post(
        f"/catalog/authors/{authors['typo']}/delete", data={"confirm": "yes"}
    )
    assert response.status_code in (303, 401, 403)
    assert await exists(factory, authors["typo"])
    assert (await anonymous.get("/catalog/authors/unused")).status_code in (303, 401)
