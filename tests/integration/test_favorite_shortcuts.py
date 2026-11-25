"""Spec 017: favorite author shortcuts — stars on the book and entry pages, the empty
favorites page, and the offer after a second finished book (Principle I throughout)."""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from book_tracker.persistence.favorites import FavoriteAuthorRepository
from book_tracker.persistence.readings import ReadingEntryRepository
from tests.conftest import Factory, TestUser, signed_in

_FORM = re.compile(
    r'<form method="post" action="/authors/([0-9a-f-]{36})/favorite"[^>]*>(.*?)</form>', re.S
)


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice")


@pytest.fixture
async def ben(factory: Factory) -> TestUser:
    return await factory.user("ben")


@pytest.fixture
async def member(
    client_factory: Callable[[], httpx.AsyncClient], alice: TestUser
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


@pytest.fixture
async def other(
    client_factory: Callable[[], httpx.AsyncClient], ben: TestUser
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), ben)


def words(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def forms(page: str) -> list[dict[str, str]]:
    """Every favorite form on the page: author, favorite, back, and the button's words."""
    found = []
    for author, body in _FORM.findall(page):
        fields = dict(re.findall(r'<input type="hidden" name="(\w+)" value="([^"]*)"', body))
        button = re.search(r"<button[^>]*>(.*?)</button>", body, re.S)
        assert button, body
        found.append(
            {
                "author": author,
                "favorite": fields.get("favorite", ""),
                "back": html.unescape(fields.get("back", "")),
                "csrf": fields.get("csrf_token", ""),
                "button": button.group(1),
                "label": words(re.sub(r'<span aria-hidden="true">.*?</span>', "", button.group(1))),
            }
        )
    return found


def query(location: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(location).query, keep_blank_values=True)


def offer_text(page: str) -> str:
    match = re.search(r'<div[^>]*class="[^"]*favorite-offer[^"]*"[^>]*>(.*?)</div>', page, re.S)
    return words(match.group(1)) if match else ""


async def favorites_of(app: Any, user: TestUser) -> set[uuid.UUID]:
    async with app.state.db.sessionmaker() as db:
        return {a.id for a in await FavoriteAuthorRepository(db, user.id).list()}


ENTRY_FIELDS = {"times_read": "1", "notes": "", "pre_ordered": ""}


async def finish(client: httpx.AsyncClient, entry: uuid.UUID, **extra: str) -> httpx.Response:
    data = {**ENTRY_FIELDS, "status": "finished", "finished_on": "2026-11-20", **extra}
    response = await client.post(f"/entries/{entry}", data=data)
    assert response.status_code == 303, response.text
    return response


# --------------------------------------------------------------------------- repositories


@pytest.mark.ac("017/AC-13")
async def test_among_is_bound_to_one_member(
    app: Any, factory: Factory, alice: TestUser, ben: TestUser
) -> None:
    a = await factory.author("Terry Pratchett", alice)
    b = await factory.author("Neil Gaiman", alice)
    c = await factory.author("Jim Butcher", alice)
    await factory.favorite(alice, a)
    await factory.favorite(ben, b)
    async with app.state.db.sessionmaker() as db:
        repo = FavoriteAuthorRepository(db, alice.id)
        assert await repo.among([a, b, c]) == {a}
        assert await repo.among([]) == set()


@pytest.mark.ac("017/AC-09")
@pytest.mark.ac("017/AC-13")
async def test_finished_counts_only_my_finished_books(
    app: Any, factory: Factory, alice: TestUser, ben: TestUser
) -> None:
    p = await factory.author("Terry Pratchett", alice)
    g = await factory.author("Neil Gaiman", alice)
    e = await factory.author("Editor", alice)
    mort = await factory.book("Mort", alice, author_ids=[p])
    small = await factory.book("Small Gods", alice, author_ids=[p])
    omens = await factory.book("Good Omens", alice, author_ids=[p, g])
    want = await factory.book("Coraline", alice, author_ids=[g])
    pyr = await factory.book("Pyramids", alice, author_ids=[p])
    anthology = await factory.book("Anthology", alice, author_ids=[e])
    series = await factory.series("Tales", alice)
    await factory.story("A Tale", alice, series_id=series, series_number="1",
                        author_ids=[g], book_ids=[anthology])  # fmt: skip
    await factory.entry(alice, mort, times_read=3)  # a re-read is still one book
    await factory.entry(alice, small)
    await factory.entry(alice, omens, status="reading")
    await factory.entry(alice, want, status="want_to_read")
    await factory.entry(alice, anthology)
    await factory.entry(ben, pyr)
    await factory.entry(ben, omens)
    async with app.state.db.sessionmaker() as db:
        counts = await ReadingEntryRepository(db, alice.id).finished_counts([p, g, e])
        assert counts.get(p) == 2
        assert counts.get(g, 0) == 0  # Reading, Want to read, and a story's author
        assert counts.get(e) == 1
        assert await ReadingEntryRepository(db, alice.id).finished_counts([]) == {}


# --------------------------------------------------------------------------- US1 stars


@pytest.fixture
async def omens(factory: Factory, alice: TestUser, ben: TestUser) -> dict[str, uuid.UUID]:
    p = await factory.author("Terry Pratchett", alice)
    g = await factory.author("Neil Gaiman", alice)
    book = await factory.book("Good Omens", alice, author_ids=[p, g])
    entry = await factory.entry(alice, book)
    await factory.favorite(alice, g)
    other_book = await factory.book("Coraline", ben, author_ids=[g])
    ben_entry = await factory.entry(ben, other_book)
    return {"p": p, "g": g, "book": book, "entry": entry, "ben_entry": ben_entry}


@pytest.mark.ac("017/AC-01")
@pytest.mark.ac("017/AC-04")
async def test_book_page_byline_has_a_star_per_author(
    member: httpx.AsyncClient, omens: dict[str, uuid.UUID]
) -> None:
    page = (await member.get(f"/books/{omens['book']}")).text
    byline = re.search(r'<div class="book-byline">(.*?)</div>', page, re.S)
    assert byline, page
    stars = forms(byline.group(1))
    assert [s["author"] for s in stars] == [str(omens["p"]), str(omens["g"])]
    p, g = stars
    assert p["favorite"] == "yes" and "☆" in p["button"] and "★" not in p["button"]
    assert p["label"] == "Add Terry Pratchett to my favorite authors"
    assert g["favorite"] == "no" and "★" in g["button"]
    assert g["label"] == "Remove Neil Gaiman from my favorite authors"
    assert p["back"] == f"/books/{omens['book']}" and p["csrf"]
    assert re.search(r'<span aria-hidden="true">[☆★]</span>', p["button"])
    # each star comes straight after its author's link
    pattern = (
        rf'<a href="/authors/{omens["p"]}">Terry Pratchett</a>\s*<form[^>]*/authors/{omens["p"]}/'
    )
    assert re.search(pattern, byline.group(1))


@pytest.mark.ac("017/AC-02")
async def test_entry_page_more_has_stars(
    member: httpx.AsyncClient, omens: dict[str, uuid.UUID]
) -> None:
    page = (await member.get(f"/entries/{omens['entry']}")).text
    more = page.split('id="more-heading"', 1)[1]
    stars = forms(more)
    assert [(s["author"], s["favorite"]) for s in stars] == [
        (str(omens["p"]), "yes"),
        (str(omens["g"]), "no"),
    ]
    assert all(s["back"] == f"/entries/{omens['entry']}" for s in stars)
    assert re.search(
        rf'All books by (?:<span[^>]*>)?<a href="/authors/{omens["p"]}">'
        r"Terry Pratchett</a>\s*<form",
        more,
    )


@pytest.mark.ac("017/AC-03")
async def test_star_adds_and_removes_and_returns(
    app: Any, member: httpx.AsyncClient, alice: TestUser, omens: dict[str, uuid.UUID]
) -> None:
    book, p = omens["book"], omens["p"]
    added = await member.post(
        f"/authors/{p}/favorite", data={"favorite": "yes", "back": f"/books/{book}"}
    )
    assert added.status_code == 303
    assert added.headers["location"] == f"/books/{book}?favorited={p}#favorite-notice"
    page = (await member.get(added.headers["location"])).text
    notice = re.search(r'<p[^>]*id="favorite-notice"[^>]*>(.*?)</p>', page, re.S)
    assert notice and words(notice.group(1)) == "Added Terry Pratchett to your favorite authors."
    assert 'role="status"' in notice.group(0)
    assert forms(page)[0]["favorite"] == "no"
    assert p in await favorites_of(app, alice)

    removed = await member.post(
        f"/authors/{p}/favorite", data={"favorite": "no", "back": f"/entries/{omens['entry']}"}
    )
    assert removed.headers["location"] == (
        f"/entries/{omens['entry']}?unfavorited={p}#favorite-notice"
    )
    page = (await member.get(removed.headers["location"])).text
    assert "Removed Terry Pratchett from your favorite authors." in words(page)
    assert p not in await favorites_of(app, alice)


@pytest.mark.ac("017/AC-05")
@pytest.mark.parametrize(
    "back",
    [
        "https://evil.example/",
        "//evil.example/books",
        "/catalog/books/{book}/edit",
        "/entries/{ben_entry}",
        "/entries/{unknown}",
        "/books/{book}/../../catalog",
        "/books/not-a-uuid",
        "",
        "x" * 2100,
    ],
)
async def test_refused_back_returns_to_the_author_page(
    member: httpx.AsyncClient, omens: dict[str, uuid.UUID], back: str
) -> None:
    back = back.format(book=omens["book"], ben_entry=omens["ben_entry"], unknown=uuid.uuid4())
    response = await member.post(
        f"/authors/{omens['p']}/favorite", data={"favorite": "yes", "back": back}
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/authors/{omens['p']}?msg=favorited"


@pytest.mark.ac("017/AC-05")
async def test_without_back_unchanged_and_unknown_author_404(
    member: httpx.AsyncClient, omens: dict[str, uuid.UUID]
) -> None:
    response = await member.post(f"/authors/{omens['p']}/favorite", data={"favorite": "yes"})
    assert response.headers["location"] == f"/authors/{omens['p']}?msg=favorited"
    missing = await member.post(
        f"/authors/{uuid.uuid4()}/favorite",
        data={"favorite": "yes", "back": f"/books/{omens['book']}"},
    )
    assert missing.status_code == 404


@pytest.mark.ac("017/AC-05")
async def test_accepted_back_keeps_its_query_without_one_time_keys(
    member: httpx.AsyncClient, omens: dict[str, uuid.UUID]
) -> None:
    p, book = omens["p"], omens["book"]
    series = uuid.uuid4()
    cases = {
        f"/?status=finished&msg=added&finished={book}&wanted={book}": "/",
        f"/series/{series}?added={omens['entry']}&finished={book}": f"/series/{series}",
        f"/books/add?after={omens['entry']}&finished={book}": "/books/add",
        f"/authors/{p}?msg=favorited": f"/authors/{p}",
        f"/books/{book}?unfavorited={p}&already={book}": f"/books/{book}",
    }
    for back, path in cases.items():
        response = await member.post(
            f"/authors/{p}/favorite", data={"favorite": "yes", "back": back}
        )
        location = response.headers["location"]
        assert location.startswith(path + "?") and location.endswith("#favorite-notice"), location
        kept = query(location)
        assert kept["favorited"] == [str(p)]
        for key in ("msg", "wanted", "already", "added", "unfavorited"):
            assert key not in kept, (back, location)
    kept = query(
        (await member.post(f"/authors/{p}/favorite", data={"favorite": "yes",
         "back": f"/?status=finished&finished={book}"})).headers["location"]
    )  # fmt: skip
    assert kept["status"] == ["finished"] and kept["finished"] == [str(book)]
    after = query(
        (await member.post(f"/authors/{p}/favorite", data={"favorite": "yes",
         "back": f"/books/add?after={omens['entry']}"})).headers["location"]
    )  # fmt: skip
    assert after["after"] == [str(omens["entry"])]


@pytest.mark.ac("017/AC-03")
async def test_invalid_notice_value_shows_nothing(
    member: httpx.AsyncClient, omens: dict[str, uuid.UUID]
) -> None:
    for value in ("nonsense", str(uuid.uuid4())):
        page = await member.get(f"/books/{omens['book']}", params={"favorited": value})
        assert page.status_code == 200
        assert 'id="favorite-notice"' not in page.text


@pytest.mark.ac("017/AC-01")
async def test_pen_name_star_favorites_the_pen_name(
    app: Any, factory: Factory, member: httpx.AsyncClient, alice: TestUser
) -> None:
    pen = await factory.author(
        "Robert Galbraith", alice, is_pen_name=True, real_name="J. K. Rowling"
    )
    book = await factory.book("The Cuckoo's Calling", alice, author_ids=[pen])
    page = (await member.get(f"/books/{book}")).text
    (star,) = forms(page.split('class="book-byline"', 1)[1].split("</div>", 1)[0])
    assert star["author"] == str(pen)
    assert star["label"] == "Add Robert Galbraith to my favorite authors"
    await member.post(
        f"/authors/{pen}/favorite", data={"favorite": "yes", "back": f"/books/{book}"}
    )
    assert await favorites_of(app, alice) == {pen}


@pytest.mark.ac("017/AC-03")
async def test_star_after_author_left_the_book_still_works(
    app: Any, factory: Factory, member: httpx.AsyncClient, alice: TestUser,
    omens: dict[str, uuid.UUID],
) -> None:  # fmt: skip
    await factory.execute(
        "DELETE FROM book_author WHERE book_id = :b AND author_id = :a",
        b=omens["book"], a=omens["p"],
    )  # fmt: skip
    response = await member.post(
        f"/authors/{omens['p']}/favorite",
        data={"favorite": "yes", "back": f"/books/{omens['book']}"},
    )
    assert response.headers["location"].startswith(f"/books/{omens['book']}?")
    assert omens["p"] in await favorites_of(app, alice)
    page = (await member.get(response.headers["location"])).text
    assert "Added Terry Pratchett to your favorite authors." in words(page)


# --------------------------------------------------------------------------- US2 empty page


@pytest.mark.ac("017/AC-06")
async def test_empty_favorites_page_leads_to_the_catalog(
    factory: Factory, member: httpx.AsyncClient, alice: TestUser
) -> None:
    page = (await member.get("/authors/favorites")).text
    text = words(page)
    assert "You haven't chosen any favorite authors yet." in text
    assert "star next to an author's name on a book page" in text
    assert re.search(r'<a href="/catalog">Browse the Catalog</a>', page)
    author = await factory.author("Terry Pratchett", alice)
    await factory.favorite(alice, author)
    page = (await member.get("/authors/favorites")).text
    assert "Browse the Catalog" not in page and "Terry Pratchett" in page


# --------------------------------------------------------------------------- US3 the offer


@pytest.fixture
async def discworld(factory: Factory, alice: TestUser) -> dict[str, uuid.UUID]:
    p = await factory.author("Terry Pratchett", alice)
    mort = await factory.book("Mort", alice, author_ids=[p])
    small = await factory.book("Small Gods", alice, author_ids=[p])
    third = await factory.book("Pyramids", alice, author_ids=[p])
    series = await factory.series("Discworld", alice)
    return {
        "p": p, "mort": mort, "small": small, "third": third, "series": series,
        "e_mort": await factory.entry(alice, mort),
        "e_small": await factory.entry(alice, small, status="reading"),
    }  # fmt: skip


@pytest.mark.ac("017/AC-07")
async def test_finishing_a_second_book_offers_the_author(
    member: httpx.AsyncClient, discworld: dict[str, uuid.UUID]
) -> None:
    saved = await finish(member, discworld["e_small"])
    location = saved.headers["location"]
    assert query(location)["finished"] == [str(discworld["small"])]
    page = (await member.get(location)).text
    assert offer_text(page).startswith("You've finished 2 books by Terry Pratchett.")
    (offer,) = [f for f in forms(page) if f["back"].startswith(f"/entries/{discworld['e_small']}?")]
    assert offer["author"] == str(discworld["p"]) and offer["favorite"] == "yes"
    assert offer["label"] == "Add Terry Pratchett to my favorite authors"
    assert query(offer["back"])["finished"] == [str(discworld["small"])]
    assert offer["csrf"]


@pytest.mark.ac("017/AC-08")
async def test_each_qualifying_author_gets_a_button(
    factory: Factory, member: httpx.AsyncClient, alice: TestUser
) -> None:
    p = await factory.author("Terry Pratchett", alice)
    g = await factory.author("Neil Gaiman", alice)
    e = await factory.author("Someone Else", alice)
    await factory.entry(alice, await factory.book("Mort", alice, author_ids=[p]))
    await factory.entry(alice, await factory.book("Coraline", alice, author_ids=[g]))
    omens = await factory.book("Good Omens", alice, author_ids=[p, g, e])
    entry = await factory.entry(alice, omens, status="reading")
    page = (await member.get((await finish(member, entry)).headers["location"])).text
    text = offer_text(page)
    assert "You've finished 2 books by Terry Pratchett." in text
    assert "You've finished 2 books by Neil Gaiman." in text
    assert "Someone Else" not in text
    offered = [f["author"] for f in forms(page) if "finished=" in f["back"]]
    assert offered == [str(p), str(g)]


@pytest.mark.ac("017/AC-09")
async def test_no_offer_when_it_does_not_apply(
    factory: Factory, member: httpx.AsyncClient, alice: TestUser,
    discworld: dict[str, uuid.UUID],
) -> None:  # fmt: skip
    # a first finished book by an author
    lone = await factory.author("Lone Author", alice)
    first = await factory.entry(
        alice, await factory.book("Only One", alice, author_ids=[lone]), status="reading"
    )
    page = (await member.get((await finish(member, first)).headers["location"])).text
    assert offer_text(page) == ""
    # saving an already-finished entry, or a change to Reading: no finished key
    again = await finish(member, discworld["e_mort"])
    assert "finished" not in query(again.headers["location"])
    reading = await member.post(
        f"/entries/{discworld['e_small']}",
        data={**ENTRY_FIELDS, "status": "reading", "finished_on": ""},
    )
    assert "finished" not in query(reading.headers["location"])
    # the entry page opened without the key; a key naming an unfinished book; nonsense
    assert offer_text((await member.get(f"/entries/{discworld['e_small']}")).text) == ""
    for value in (str(discworld["small"]), str(discworld["third"]), "nonsense"):
        page = await member.get(f"/entries/{discworld['e_small']}", params={"finished": value})
        assert page.status_code == 200 and offer_text(page.text) == "", value
    # a favorite is never offered
    await factory.favorite(alice, discworld["p"])
    page = (await member.get((await finish(member, discworld["e_small"])).headers["location"])).text
    assert offer_text(page) == ""


@pytest.mark.ac("017/AC-09")
async def test_finishing_a_reread_counts_one_book(
    factory: Factory, member: httpx.AsyncClient, alice: TestUser
) -> None:
    lone = await factory.author("Lone Author", alice)
    entry = await factory.entry(alice, await factory.book("Only One", alice, author_ids=[lone]))
    assert (await member.post(f"/entries/{entry}/read-again")).status_code == 303
    location = (await finish(member, entry, times_read="1")).headers["location"]
    assert "finished" in query(location)
    assert offer_text((await member.get(location)).text) == ""


@pytest.mark.ac("017/AC-09")
async def test_reload_shows_the_offer_only_while_true(
    factory: Factory, member: httpx.AsyncClient, alice: TestUser,
    discworld: dict[str, uuid.UUID],
) -> None:  # fmt: skip
    location = (await finish(member, discworld["e_small"])).headers["location"]
    assert offer_text((await member.get(location)).text)
    assert offer_text((await member.get(location)).text)  # a reload: still true
    await factory.favorite(alice, discworld["p"])
    assert offer_text((await member.get(location)).text) == ""


@pytest.mark.ac("017/AC-10")
async def test_accepting_the_offer(
    app: Any, factory: Factory, client_factory: Callable[[], httpx.AsyncClient],
    member: httpx.AsyncClient, alice: TestUser,
) -> None:  # fmt: skip
    p = await factory.author("Terry Pratchett", alice)
    g = await factory.author("Neil Gaiman", alice)
    await factory.entry(alice, await factory.book("Mort", alice, author_ids=[p]))
    await factory.entry(alice, await factory.book("Coraline", alice, author_ids=[g]))
    omens = await factory.book("Good Omens", alice, author_ids=[p, g])
    entry = await factory.entry(alice, omens, status="reading")
    bare = await signed_in(client_factory(), alice)
    page = (await bare.get((await finish(member, entry)).headers["location"])).text
    offer = next(f for f in forms(page) if f["author"] == str(p) and "finished=" in f["back"])
    del bare.headers["X-CSRF-Token"]  # the form's own token only
    refused = await bare.post(
        f"/authors/{p}/favorite", data={"favorite": "yes", "back": offer["back"]}
    )
    assert refused.status_code in (400, 403)
    assert p not in await favorites_of(app, alice)

    accepted = await bare.post(
        f"/authors/{p}/favorite",
        data={"csrf_token": offer["csrf"], "favorite": offer["favorite"], "back": offer["back"]},
    )
    assert accepted.status_code == 303
    location = accepted.headers["location"]
    assert location.startswith(f"/entries/{entry}?") and location.endswith("#favorite-notice")
    assert p in await favorites_of(app, alice)
    page = (await member.get(location)).text
    assert "Added Terry Pratchett to your favorite authors." in words(page)
    text = offer_text(page)
    assert "Terry Pratchett" not in text and "You've finished 2 books by Neil Gaiman." in text


@pytest.mark.ac("017/AC-11")
async def test_ignoring_stores_nothing_and_offers_again(
    app: Any, factory: Factory, member: httpx.AsyncClient, alice: TestUser,
    discworld: dict[str, uuid.UUID],
) -> None:  # fmt: skip
    await member.get((await finish(member, discworld["e_small"])).headers["location"])
    assert await favorites_of(app, alice) == set()
    third = await factory.entry(alice, discworld["third"], status="reading")
    page = (await member.get((await finish(member, third)).headers["location"])).text
    assert offer_text(page).startswith("You've finished 3 books by Terry Pratchett.")


def _add(book: uuid.UUID, title: str, **extra: str) -> dict[str, str]:
    return {"book_id": str(book), "title": title, "status": "finished",
            "finished_on": "2026-11-20", **extra}  # fmt: skip


@pytest.mark.ac("017/AC-12")
async def test_adding_a_finished_book_offers_on_every_landing_page(
    factory: Factory, member: httpx.AsyncClient, alice: TestUser,
    discworld: dict[str, uuid.UUID],
) -> None:  # fmt: skip
    p = discworld["p"]
    cases = [
        ({}, "/"),
        ({"from_series": str(discworld["series"])}, f"/series/{discworld['series']}"),
        ({"then": "another"}, "/books/add"),
        ({"dropped_stories": "yes"}, "/entries/"),
    ]
    for extra, path in cases:
        await factory.execute("DELETE FROM reading_entry WHERE book_id = :b", b=discworld["third"])
        response = await member.post(
            "/books/add", data=_add(discworld["third"], "Pyramids", **extra)
        )
        assert response.status_code == 303, response.text
        location = response.headers["location"]
        assert location.startswith(path), location
        assert query(location)["finished"] == [str(discworld["third"])], location
        page = (await member.get(location)).text
        assert offer_text(page).startswith("You've finished 2 books by Terry Pratchett."), path
        assert any(f["author"] == str(p) and "finished=" in f["back"] for f in forms(page)), path
    # the HTMX list partial carries no offer
    fragment = await member.get("/", params={"finished": str(discworld["third"])},
                                headers={"HX-Request": "true"})  # fmt: skip
    assert "favorite-offer" not in fragment.text
    # adding as Want to read: no key
    await factory.execute("DELETE FROM reading_entry WHERE book_id = :b", b=discworld["third"])
    wanted = await member.post(
        "/books/add",
        data=_add(discworld["third"], "Pyramids", status="want_to_read", finished_on=""),
    )
    assert "finished" not in query(wanted.headers["location"])


# --------------------------------------------------------------------------- US4 privacy


@pytest.mark.ac("017/AC-13")
async def test_another_members_favorites_and_books_never_count(
    factory: Factory, member: httpx.AsyncClient, alice: TestUser, ben: TestUser,
    discworld: dict[str, uuid.UUID],
) -> None:  # fmt: skip
    p = discworld["p"]
    await factory.favorite(ben, p)
    for book in (discworld["small"], discworld["third"]):
        await factory.entry(ben, book)
    page = (await member.get(f"/books/{discworld['mort']}")).text
    (star,) = forms(page.split('class="book-byline"', 1)[1].split("</div>", 1)[0])
    assert star["favorite"] == "yes" and "☆" in star["button"]
    # Alice: Mort finished, Small Gods finishing → 2, not Ben's books on top
    page = (await member.get((await finish(member, discworld["e_small"])).headers["location"])).text
    assert offer_text(page).startswith("You've finished 2 books by Terry Pratchett.")


@pytest.mark.ac("017/AC-13")
async def test_first_book_not_offered_because_of_another_member(
    factory: Factory, member: httpx.AsyncClient, alice: TestUser, ben: TestUser
) -> None:
    p = await factory.author("Terry Pratchett", alice)
    for title in ("Mort", "Pyramids"):
        await factory.entry(ben, await factory.book(title, ben, author_ids=[p]))
    mine = await factory.entry(
        alice, await factory.book("Small Gods", alice, author_ids=[p]), status="reading"
    )
    page = (await member.get((await finish(member, mine)).headers["location"])).text
    assert offer_text(page) == ""
