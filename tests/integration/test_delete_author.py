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
@pytest.mark.ac("018/AC-08")
async def test_authors_page_links_unused_authors(
    member: httpx.AsyncClient, factory: Factory, authors: dict[str, uuid.UUID]
) -> None:
    """Spec 018 moved the link from My books to the Authors page."""
    page = await member.get("/authors")
    assert '<a href="/catalog/authors/unused">Authors with no books (2)</a>' in page.text
    partial = await member.get("/authors", headers={"HX-Request": "true"})
    assert "/catalog/authors/unused" not in partial.text
    assert "/catalog/authors/unused" not in (await member.get("/")).text
    await factory.execute(
        "DELETE FROM author WHERE id IN (:a, :b)", a=authors["typo"], b=authors["nobody"]
    )
    assert "/catalog/authors/unused" not in (await member.get("/authors")).text


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
    location = done.headers["location"]
    assert location.startswith("/catalog/authors/unused?msg=deleted&author=J+DM+Robb&sig=")
    assert not await exists(factory, authors["typo"])
    page = await member.get(location)
    assert re.search(r'role="status"[^>]*>\s*Deleted “J DM Robb”\.', page.text)
    assert "J DM Robb</a>" not in page.text
    found = await member.get("/api/v1/authors", params={"q": "Robb"})
    assert [a["name"] for a in found.json()] == ["J.D. Robb"]
    assert (await member.get(f"/catalog/authors/{authors['typo']}/edit")).status_code == 404
    # A crafted link (no valid signature) shows no message (PR #24 review).
    for crafted in (
        "/catalog/authors/unused?msg=deleted&author=Terry+Pratchett",
        "/catalog/authors/unused?msg=deleted&author=J+DM+Robb&sig=" + "0" * 64,
    ):
        assert "Deleted" not in text(await member.get(crafted)), crafted


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
    assert f'<a href="/books/{authors["glory"]}">Glory in Death</a>' in edit.text
    assert f'<a href="/books/{authors["naked"]}">Naked in Death</a>' in edit.text
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


@pytest.mark.ac("008/AC-07")
async def test_confirm_page_rechecks_books(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, authors: dict[str, uuid.UUID]
) -> None:
    """A book linked after Edit author was shown: the confirm step says so instead of
    claiming the author has none (PR #24 review)."""
    await factory.book("Typo Book", alice, author_ids=[authors["typo"]])
    asked = await member.post(f"/catalog/authors/{authors['typo']}/delete", data={})
    assert asked.status_code == 409
    assert "“J DM Robb” now has a book, so it can't be deleted." in text(asked)
    assert "from the family catalog?" not in text(asked)


@pytest.mark.ac("008/AC-07")
async def test_foreign_key_backstop(
    member: httpx.AsyncClient,
    factory: Factory,
    authors: dict[str, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the delete statement trips the foreign key (a book linked in the same instant),
    the member gets the 409 explanation, not an error page."""
    from sqlalchemy.exc import IntegrityError

    from book_tracker.persistence import catalog as persistence

    async def tripped(*_: object) -> bool:
        raise IntegrityError("DELETE FROM author", {}, Exception("book_author_author_id_fkey"))

    monkeypatch.setattr(persistence, "delete_unused_author", tripped)
    refused = await member.post(
        f"/catalog/authors/{authors['typo']}/delete", data={"confirm": "yes"}
    )
    assert refused.status_code == 409
    assert "wasn't deleted" in text(refused)
    assert await exists(factory, authors["typo"])


async def test_author_deleted_while_saving_or_adding(
    member: httpx.AsyncClient,
    factory: Factory,
    alice: TestUser,
    authors: dict[str, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PR #24 review: an author deleted between the checks and the write gives a 404 when
    saving that author, and a field error when adding a book that names it, not a 500."""
    from book_tracker.services import catalog as service

    typo = authors["typo"]
    real_get = service.get_author

    async def deleted_meanwhile(db: object, author_id: uuid.UUID) -> object:
        author = await real_get(db, author_id)  # type: ignore[arg-type]
        await factory.execute("DELETE FROM author WHERE id = :id", id=typo)
        return author

    monkeypatch.setattr(service, "get_author", deleted_meanwhile)
    saved = await member.post(
        f"/catalog/authors/{typo}/edit",
        data={"name": "J. D. M. Robb", "sort_name": "Robb, J. D. M.", "real_name": ""},
    )
    assert saved.status_code == 404
    monkeypatch.undo()

    nobody = authors["nobody"]

    async def references_ok(*_: object) -> None:
        await factory.execute("DELETE FROM author WHERE id = :id", id=nobody)

    monkeypatch.setattr(service, "_check_references", references_ok)
    added = await member.post(
        "/books/add",
        data={
            "title": "Ghost Book",
            "author_id_0": str(nobody),
            "author_name_0": "Nobody Writes",
            "status": "want_to_read",
            "then": "list",
        },  # fmt: skip
    )
    assert added.status_code == 422
    assert "An author you chose was just deleted from the catalog." in text(added)
    assert await factory.scalar("SELECT count(*) FROM book WHERE title = 'Ghost Book'") == 0
