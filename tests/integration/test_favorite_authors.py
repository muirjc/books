"""Spec 011: favorite authors — storage, the user-bound repository, pages, API, the
My books filter and the delete rule (constitution 2.0.0)."""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from book_tracker.persistence import catalog as persistence_catalog
from book_tracker.persistence import models
from book_tracker.persistence.favorites import FavoriteAuthorRepository
from book_tracker.services import catalog as catalog_service
from book_tracker.services.errors import ConflictError
from tests.conftest import Factory, signed_in, ui_csrf


@pytest.mark.ac("011/AC-11")
async def test_one_favorite_per_member_and_author(app: Any, factory: Factory) -> None:
    alice = await factory.user("alice")
    author = await factory.author("Jim Butcher", alice)
    await factory.favorite(alice, author)
    with pytest.raises(IntegrityError, match="favorite_author_pkey"):
        await factory.favorite(alice, author)


@pytest.mark.ac("011/AC-11")
async def test_author_restricted_user_cascades(app: Any, factory: Factory) -> None:
    alice = await factory.user("alice")
    author = await factory.author("Jim Butcher", alice)
    await factory.favorite(alice, author)
    with pytest.raises(IntegrityError, match="favorite_author_author_id_fkey"):
        await factory.execute("DELETE FROM author WHERE id = :a", a=author)
    rules = await factory.scalar(
        "SELECT string_agg(conname || '=' || confdeltype::text, ',' ORDER BY conname) "
        "FROM pg_constraint WHERE conrelid = 'favorite_author'::regclass AND contype = 'f'"
    )
    assert rules == "favorite_author_author_id_fkey=r,favorite_author_user_id_fkey=c"


@pytest.mark.ac("011/AC-09")
async def test_repository_is_bound_to_one_member(app: Any, factory: Factory) -> None:
    alice, ben = await factory.user("alice"), await factory.user("ben")
    butcher = await factory.author("Jim Butcher", alice, sort_name="Butcher, Jim")
    austen = await factory.author("Jane Austen", alice, sort_name="Austen, Jane")
    mine_book = await factory.book("Storm Front", alice, author_ids=[butcher])
    other_book = await factory.book("Emma", alice, author_ids=[austen])
    async with app.state.db.sessionmaker() as db:
        repo = FavoriteAuthorRepository(db, alice.id)
        assert await repo.add(butcher) is True
        assert await repo.add(butcher) is True  # already: harmless
        assert await repo.add(austen) is True
        await db.commit()
        assert [a.name for a in await repo.list()] == ["Jane Austen", "Jim Butcher"]
        assert await repo.has(butcher)
        bens = FavoriteAuthorRepository(db, ben.id)
        assert await bens.list() == [] and not await bens.has(butcher)
        assert await bens.remove(butcher) is False  # Ben can't remove Alice's
        ids = set(await db.scalars(select(models.Book.id).where(bens.condition())))
        assert ids == set()
        assert await repo.remove(austen) is True and await repo.remove(austen) is False
        await db.commit()
        ids = set(await db.scalars(select(models.Book.id).where(repo.condition())))
        assert ids == {mine_book} and other_book not in ids
        assert await repo.add(uuid.uuid4()) is False  # unknown author


# ------------------------------------------------------------------ pages (US3, US4)


@pytest.fixture
async def people(factory: Factory, client_factory: Callable[[], httpx.AsyncClient]) -> Any:
    alice, ben = await factory.user("alice"), await factory.user("ben")
    butcher = await factory.author("Jim Butcher", alice, sort_name="Butcher, Jim")
    austen = await factory.author("Jane Austen", alice, sort_name="Austen, Jane")
    lonely = await factory.author("Nobody Yet", alice, sort_name="Yet, Nobody")
    storm = await factory.book("Storm Front", alice, author_ids=[butcher])
    emma = await factory.book("Emma", alice, author_ids=[austen])
    both = await factory.book("A Shared Anthology", alice, author_ids=[austen, butcher])
    for book in (storm, emma, both):
        await factory.entry(alice, book, status="want_to_read")
        await factory.entry(ben, book, status="want_to_read")
    return SimpleNamespace(
        alice=alice, ben=ben, butcher=butcher, austen=austen, lonely=lonely,
        member=await signed_in(client_factory(), alice),
        other=await signed_in(client_factory(), ben),
    )  # fmt: skip


def _titles(body: str) -> list[str]:
    return [
        html.unescape(t)
        for t in re.findall(r'class="book-title" href="/entries/[^"]+">([^<]+)</a>', body)
    ]


@pytest.mark.ac("018/AC-04")
@pytest.mark.ac("018/AC-07")
async def test_favorites_only_replaces_my_favorite_authors(people: Any, factory: Factory) -> None:
    """Spec 018 replaced the spec 011 AC-12 page with the Authors page's Favorites only."""
    empty = (await people.member.get("/authors?favorites=1")).text
    assert "You haven't chosen any favorite authors yet." in empty
    await factory.favorite(people.alice, people.butcher)
    await factory.favorite(people.alice, people.austen)
    await factory.favorite(people.ben, people.lonely)
    page = (await people.member.get("/authors?favorites=1")).text
    assert "<h1>Authors</h1>" in page
    links = re.findall(r'<a class="row-name" href="/authors/([0-9a-f-]{36})">([^<]+)</a>', page)
    assert [name for _, name in links] == ["Jane Austen", "Jim Butcher"]  # Ben's isn't here
    home = (await people.member.get("/")).text
    assert "/authors/favorites" not in home and "/authors?favorites=1" not in home
    author = (await people.member.get(f"/authors/{people.lonely}")).text
    assert 'href="/authors?favorites=1"' in author


@pytest.mark.ac("011/AC-13")
async def test_my_books_favorites_filter(people: Any, factory: Factory) -> None:
    await factory.favorite(people.alice, people.butcher)
    await factory.favorite(people.ben, people.austen)
    home = (await people.member.get("/")).text
    first, second = '<option value="">Any author</option>', '<option value="favorites">'
    assert re.search(re.escape(first) + r"\s*" + re.escape(second) + "My favorite authors", home)
    page = (await people.member.get("/", params={"author_id": "favorites", "sort": "-title"})).text
    assert _titles(page) == ["Storm Front", "A Shared Anthology"]
    assert '<option value="favorites" selected>My favorite authors</option>' in page
    bens = (await people.other.get("/", params={"author_id": "favorites"})).text
    assert _titles(bens) == ["A Shared Anthology", "Emma"]
    bad = await people.member.get("/", params={"author_id": "nonsense"})
    assert bad.status_code == 200 and len(_titles(bad.text)) == 3


async def _delete(client: httpx.AsyncClient, author: uuid.UUID, confirm: bool) -> httpx.Response:
    data = {"csrf_token": await ui_csrf(client)}
    if confirm:
        data["confirm"] = "yes"
    return await client.post(f"/catalog/authors/{author}/delete", data=data)


MINE = (
    "This author is one of your favorite authors. Remove them from your favorites to delete them."
)
OTHERS = "A family member has this author as a favorite, so they can&#39;t be deleted."


@pytest.mark.ac("011/AC-14")
async def test_my_favorite_cant_be_deleted(people: Any, factory: Factory) -> None:
    await factory.favorite(people.alice, people.lonely)
    page = (await people.member.get(f"/catalog/authors/{people.lonely}/edit")).text
    assert MINE in page and "Delete author</button>" not in page
    assert f'href="/authors/{people.lonely}"' in page
    refused = await _delete(people.member, people.lonely, confirm=True)
    assert refused.status_code == 409 and MINE in refused.text
    assert await factory.scalar("SELECT count(*) FROM author WHERE id = :a", a=people.lonely) == 1


@pytest.mark.ac("011/AC-15")
async def test_others_favorite_blocks_without_naming_them(people: Any, factory: Factory) -> None:
    await factory.favorite(people.ben, people.lonely)
    page = (await people.member.get(f"/catalog/authors/{people.lonely}/edit")).text
    assert OTHERS in page and "Delete author</button>" not in page
    assert "ben" not in page.lower().replace("benefit", "")
    unused = (await people.member.get("/catalog/authors/unused")).text
    assert "Nobody Yet" not in unused
    home = (await people.member.get("/")).text
    assert "Authors with no books" not in home
    await factory.execute("DELETE FROM favorite_author")
    assert "Nobody Yet" in (await people.member.get("/catalog/authors/unused")).text
    page = (await people.member.get(f"/catalog/authors/{people.lonely}/edit")).text
    assert "Delete author</button>" in page


@pytest.mark.ac("011/AC-16")
async def test_favorited_between_confirm_and_delete(people: Any, factory: Factory) -> None:
    confirm = await _delete(people.member, people.lonely, confirm=False)
    assert confirm.status_code == 200 and "from the family catalog?" in confirm.text
    await factory.favorite(people.ben, people.lonely)  # meanwhile
    refused = await _delete(people.member, people.lonely, confirm=True)
    assert refused.status_code == 409 and OTHERS in refused.text
    assert await factory.scalar("SELECT count(*) FROM author WHERE id = :a", a=people.lonely) == 1
    # And a favorite asked for after the confirmation page also blocks it.
    await factory.execute("DELETE FROM favorite_author")
    await factory.favorite(people.alice, people.lonely)
    refused = await _delete(people.member, people.lonely, confirm=False)
    assert refused.status_code == 409 and MINE in refused.text


@pytest.mark.ac("011/AC-16")
async def test_restrict_key_backstops_the_delete_check(
    people: Any, app: Any, factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A favorite committed by another session after the NOT EXISTS check: the RESTRICT
    foreign key refuses the delete, and the refusal is classified as a favorite."""

    async def unguarded(db: Any, author_id: uuid.UUID) -> bool:
        await factory.favorite(people.ben, author_id)  # another member, meanwhile
        await db.execute(delete(models.Author).where(models.Author.id == author_id))
        return True

    monkeypatch.setattr(persistence_catalog, "delete_unused_author", unguarded)
    async with app.state.db.sessionmaker() as db:
        with pytest.raises(ConflictError) as raised:
            await catalog_service.delete_author(db, people.alice.id, people.lonely)
    assert raised.value.code == "author_is_favorite"


@pytest.mark.ac("011/AC-17")
async def test_favorite_for_an_author_deleted_meanwhile(people: Any, factory: Factory) -> None:
    page = await people.member.get(f"/authors/{people.lonely}")
    assert page.status_code == 200
    await factory.execute("DELETE FROM author WHERE id = :a", a=people.lonely)
    added = await people.member.post(
        f"/authors/{people.lonely}/favorite",
        data={"csrf_token": await ui_csrf(people.member), "favorite": "yes"},
    )
    assert added.status_code == 404
    assert await factory.scalar("SELECT count(*) FROM favorite_author") == 0


@pytest.mark.ac("011/AC-16")
async def test_blocker_gone_before_classifying_retries(
    people: Any, app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first delete was refused, but nothing blocks it by the time it is classified
    (say a favorite was removed): the delete is tried again (PR #30 review)."""
    real = persistence_catalog.delete_unused_author
    calls: list[int] = []

    async def refused_once(db: Any, author_id: uuid.UUID) -> bool:
        calls.append(1)
        return False if len(calls) == 1 else await real(db, author_id)

    monkeypatch.setattr(persistence_catalog, "delete_unused_author", refused_once)
    async with app.state.db.sessionmaker() as db:
        await catalog_service.delete_author(db, people.alice.id, people.lonely)
        await db.commit()
    assert len(calls) == 2
    async with app.state.db.sessionmaker() as db:
        assert await persistence_catalog.get_author(db, people.lonely) is None


@pytest.mark.ac("011/AC-16")
async def test_refusal_says_why_even_if_the_favorite_is_gone(
    people: Any, factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A favorite blocked the delete but was removed before the page was drawn: the page
    still says why it wasn't deleted, and names nobody."""

    async def blocked(db: Any, actor: uuid.UUID, author_id: uuid.UUID) -> None:
        raise ConflictError("author_is_favorite", "A family member has this author as a favorite")

    monkeypatch.setattr(catalog_service, "delete_author", blocked)
    refused = await _delete(people.member, people.lonely, confirm=True)
    assert refused.status_code == 409
    assert OTHERS in refused.text
