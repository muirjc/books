"""Spec 016: the read-only book page (books-d9u).

Contract: specs/016-book-page/contracts/ui-book-page.md.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, TestUser, ui_csrf
from tests.integration.test_book_rows import row
from tests.integration.test_flow_fixes import link, text_of
from tests.integration.test_quick_add import (  # noqa: F401
    alice_fixture,
    member_fixture,
    plain,
    quick_add,
    quick_button,
    world_fixture,
)


async def summary(factory: Factory, book: uuid.UUID, by: TestUser, text: str) -> None:
    await factory.execute(
        "INSERT INTO book_summary (id, book_id, text, origin, created_by, is_current) "
        "VALUES (gen_random_uuid(), :b, :t, 'manual', :u, true)",
        b=book, t=text, u=by.id,
    )  # fmt: skip


def section(page: str, heading_id: str) -> str:
    found = re.search(rf'<section aria-labelledby="{heading_id}".*?</section>', page, re.S)
    assert found, heading_id
    return found.group(0)


@pytest.mark.ac("016/AC-01")
@pytest.mark.ac("016/AC-05")
async def test_book_details_in_order(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    pen = await factory.author("Pen Person", alice, is_pen_name=True, real_name="Real Person")
    book = await factory.book("Small Things", alice, author_ids=[w["terry"], pen],
                              series_id=w["disc"], series_number="13.5",
                              release_date=date(2020, 5, 1))  # fmt: skip
    await factory.execute(
        "INSERT INTO book_source_ref (id, book_id, source, source_work_id, imported_by) "
        "VALUES (gen_random_uuid(), :b, 'open_library', 'OL9W', :u)", b=book, u=alice.id,
    )  # fmt: skip
    response = await member.get(f"/books/{book}")
    assert response.status_code == 200
    page = response.text
    heading = page.find(f'<h1 id="book-{book}">Small Things</h1>')
    authors = page.find(f'href="/authors/{w["terry"]}"')
    series = page.find(f'href="/series/{w["disc"]}"')
    released = page.find("Released 1 May 2020")
    source = page.find("OL9W")
    assert -1 < heading < authors < series < released < source, (heading, authors, series,
                                                                  released, source)  # fmt: skip
    assert "pen name of Real Person" in text_of(page)
    assert "Discworld #13.5" in text_of(page)
    main = page[page.find("<main") :]
    # Read-only: no field that changes the book (only the quick add and summary draft forms).
    assert not re.search(r'<(?:input|textarea|select)(?![^>]*type="hidden")', main), main
    assert link(page, "Edit book") == f"/catalog/books/{book}/edit"
    assert link(page, "Terry Pratchett") == f"/authors/{w['terry']}"


@pytest.mark.ac("016/AC-01")
async def test_upcoming_and_undated_release(member: httpx.AsyncClient, w: dict[str, Any]) -> None:
    soon = text_of((await member.get(f"/books/{w['soon']}")).text)
    assert "Coming" in soon and "Released" not in soon
    undated = text_of((await member.get(f"/books/{w['gods']}")).text)
    assert "Coming" not in undated and "Released" not in undated


@pytest.mark.ac("016/AC-02")
async def test_summary_or_none(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    page = (await member.get(f"/books/{w['gods']}")).text
    part = section(page, "summary-heading")
    assert "No summary yet." in text_of(part)
    assert link(part, "Write a summary") == f"/catalog/books/{w['gods']}/summary"
    assert f'action="/catalog/books/{w["gods"]}/summary/draft"' in part
    assert "Draft with AI" in text_of(part)
    await summary(factory, w["gods"], alice, "Gods need believers.")
    part = section((await member.get(f"/books/{w['gods']}")).text, "summary-heading")
    assert "Gods need believers." in text_of(part)
    assert re.search(r"Written by Alice on \d{1,2} \w{3} \d{4}", text_of(part))
    assert link(part, "Write a new summary") == f"/catalog/books/{w['gods']}/summary"


@pytest.mark.ac("016/AC-03")
async def test_my_status_or_add(
    member: httpx.AsyncClient, factory: Factory, w: dict[str, Any]
) -> None:
    await factory.execute(
        "UPDATE reading_entry SET status = 'finished', finished_on = '2025-03-03' WHERE id = :e",
        e=w["mort_entry"],
    )
    mine = section((await member.get(f"/books/{w['mort']}")).text, "my-reading-heading")
    assert re.search(
        rf'<a class="badge status-link" href="/entries/{w["mort_entry"]}">Finished', mine
    )
    assert "3 Mar 2025" in text_of(mine)
    assert link(mine, "Open my entry") == f"/entries/{w['mort_entry']}"
    assert not quick_button(mine, w["mort"])
    other = section((await member.get(f"/books/{w['gods']}")).text, "my-reading-heading")
    assert "Not on my list" in text_of(other)
    form = quick_button(other, w["gods"])
    assert form and f'name="back" value="/books/{w["gods"]}"' in form.group(0)
    assert re.search(rf'href="/books/add\?book={w["gods"]}"', other)
    assert "Open my entry" not in text_of(other)


@pytest.mark.ac("016/AC-04")
@pytest.mark.ac("016/AC-10")
async def test_quick_add_returns_to_the_book_page(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    back = f"/books/{w['gods']}"
    response = await quick_add(member, w["gods"], back)
    assert response.status_code == 303
    assert response.headers["location"] == f"{back}?wanted={w['gods']}#book-{w['gods']}"
    page = (await member.get(response.headers["location"])).text
    assert "Added “Small Gods” to your list as Want to read." in plain(page)
    assert re.search(r'class="badge status-link"[^>]*>Want to read', page)
    again = await quick_add(member, w["gods"], back)
    assert again.headers["location"] == f"{back}?already={w['gods']}#book-{w['gods']}"
    assert "“Small Gods” is already on your list." in plain(
        (await member.get(again.headers["location"])).text
    )
    status = await factory.scalar(
        "SELECT status FROM reading_entry WHERE user_id = :u AND book_id = :b",
        u=alice.id, b=w["gods"],
    )  # fmt: skip
    assert status == "want_to_read"


@pytest.mark.ac("016/AC-10")
async def test_only_the_book_page_is_a_new_return_address(
    member: httpx.AsyncClient, w: dict[str, Any]
) -> None:
    for back in ("/books/add", f"/books/{w['gods']}/edit", f"/books/{w['gods']}x",
                 f"//evil.example/books/{w['gods']}", "/books/not-a-uuid"):  # fmt: skip
        response = await quick_add(member, w["tales"], back)
        assert response.headers["location"].startswith("/catalog?"), back


@pytest.mark.ac("016/AC-06")
async def test_missing_book_and_signed_out(member: httpx.AsyncClient, client_factory: Any) -> None:
    assert (await member.get(f"/books/{uuid.uuid4()}")).status_code == 404
    assert (await member.get("/books/not-a-uuid")).status_code in {404, 422}
    anonymous = await client_factory().get(f"/books/{uuid.uuid4()}")
    assert anonymous.status_code in {302, 303} and "/sign-in" in anonymous.headers["location"]


# --- User Story 2: titles open the book page -------------------------------------------


@pytest.mark.ac("016/AC-07")
async def test_titles_open_the_book_page(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    await factory.entry(alice, w["soon"], status="want_to_read")
    for path, books in {
        "/catalog": ["gods", "mort"],
        f"/authors/{w['terry']}": ["gods", "mort"],
        "/upcoming": ["soon"],
    }.items():
        page = (await member.get(path)).text
        for name in books:
            found = row(page, w[name])
            assert re.search(rf'<a class="book-title" href="/books/{w[name]}">', found), (
                path,
                name,
            )
    catalog = (await member.get("/catalog")).text
    assert f'<a class="badge status-link" href="/entries/{w["mort_entry"]}">' in row(
        catalog, w["mort"]
    )  # the badge still opens my entry
    # Upcoming's "Also coming" section, for a book not on my list.
    later = await factory.book("Later On", alice, author_ids=[w["terry"]],
                               release_date=date(2099, 1, 1))  # fmt: skip
    upcoming = (await member.get("/upcoming")).text
    assert f'<a class="book-title" href="/books/{later}">' in row(upcoming, later)


@pytest.mark.ac("016/AC-07")
async def test_series_and_edit_lists_link_to_the_book_page(
    member: httpx.AsyncClient, w: dict[str, Any]
) -> None:
    series = (await member.get(f"/series/{w['disc']}")).text
    for name in ("gods", "mort"):
        assert re.search(rf'<a class="book-title" href="/books/{w[name]}">', series), name
    story = re.search(r'<li class="series-story"[^>]*>.*?</li>', series, re.S)
    assert story and f'<a href="/books/{w["tales"]}">Disc Tales</a>' in story.group(0)
    for path in (f"/catalog/authors/{w['terry']}/edit", f"/catalog/series/{w['disc']}/edit"):
        page = (await member.get(path)).text
        assert f'href="/books/{w["gods"]}"' in page, path
        assert f'href="/catalog/books/{w["gods"]}/edit"' not in page, path


@pytest.mark.ac("016/AC-08")
async def test_my_books_titles_still_open_my_entry(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    page = (await member.get("/")).text
    assert f'<a class="book-title" href="/entries/{w["mort_entry"]}">Mort</a>' in page
    assert f'href="/books/{w["mort"]}"' not in page
    # Spec 018 moved the Now out list to Upcoming; My books keeps only a pointer to it.
    out = await factory.book("Just Out", alice, author_ids=[w["terry"]], release_date=date.today())
    await factory.entry(alice, out, status="want_to_read", pre_ordered=True)
    page = (await member.get("/")).text
    assert '<a href="/upcoming#now-out">1 book you want to read is now out</a>' in page
    assert f'href="/books/{out}"' not in page


@pytest.mark.ac("016/AC-09")
async def test_entry_and_edit_book_link_to_the_book_page(
    member: httpx.AsyncClient, w: dict[str, Any]
) -> None:
    entry = (await member.get(f"/entries/{w['mort_entry']}")).text
    assert link(entry, "View the book page") == f"/books/{w['mort']}"
    edit = (await member.get(f"/catalog/books/{w['gods']}/edit")).text
    assert link(edit, "View the book page") == f"/books/{w['gods']}"
    # Spec edge case: Edit book's back link is unchanged (spec 014 AC-06).
    assert link(edit, "Back to the catalog") == "/catalog"
    mine = (await member.get(f"/catalog/books/{w['mort']}/edit")).text
    assert link(mine, "Back to “Mort”") == f"/entries/{w['mort_entry']}"


# --- User Story 3: collections ---------------------------------------------------------


@pytest.mark.ac("016/AC-11")
async def test_stories_with_also_in(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    omnibus = await factory.book("Disc Omnibus", alice, author_ids=[w["terry"]])
    await factory.story("Sea and Little Fishes", alice, series_id=w["disc"], series_number="23.5",
                        author_ids=[w["terry"]], book_ids=[w["tales"], omnibus])  # fmt: skip
    page = (await member.get(f"/books/{w['tales']}")).text
    part = section(page, "stories-heading")
    lines = re.findall(r"<li>.*?</li>", part, re.S)
    assert [text_of(x).split(" · ")[0] for x in lines] == [
        "#4.5 Discworld — Troll Bridge",
        "#23.5 Discworld — Sea and Little Fishes",
    ]
    assert f'href="/series/{w["disc"]}"' in lines[0]
    assert "Also in" not in text_of(lines[0])
    assert "Also in “Disc Omnibus”" in plain(lines[1])
    assert link(lines[1], "Disc Omnibus") == f"/books/{omnibus}"
    assert f'href="/books/{w["tales"]}"' not in part  # never the book itself
    # The entry page and Edit book are unchanged: no "Also in".
    entry = await factory.entry(alice, w["tales"], status="reading")
    for path in (f"/entries/{entry}", f"/catalog/books/{w['tales']}/edit"):
        assert "Also in" not in text_of((await member.get(path)).text), path


@pytest.mark.ac("016/AC-12")
async def test_add_a_story_from_the_book_page(member: httpx.AsyncClient, w: dict[str, Any]) -> None:
    page = (await member.get(f"/books/{w['gods']}")).text
    part = section(page, "stories-heading")
    assert "No stories recorded" in text_of(part)
    add = link(part, "Add a story")
    assert add == f"/catalog/books/{w['gods']}/stories/add?from=page"
    form = (await member.get(add)).text
    assert link(form, "Cancel") == f"/books/{w['gods']}"
    assert 'name="from" value="page"' in form
    data = {"csrf_token": await ui_csrf(member), "from": "page", "title": "Small Story",
            "series_number": "13.25", "author_name_0": "Terry Pratchett",
            "author_id_0": str(w["terry"]), "series_name": "Discworld",
            "series_id": str(w["disc"])}  # fmt: skip
    saved = await member.post(f"/catalog/books/{w['gods']}/stories/add", data=data)
    assert saved.status_code == 303, saved.text
    assert saved.headers["location"] == f"/books/{w['gods']}?msg=story_added#stories-heading"
    after = (await member.get(saved.headers["location"])).text
    assert "Story added." in text_of(after)
    assert "Small Story" in text_of(section(after, "stories-heading"))
    another = await member.post(f"/catalog/books/{w['gods']}/stories/add",
                                data={**data, "title": "Other Story", "series_number": "13.75",
                                      "then": "another"})  # fmt: skip
    assert "from=page" in another.headers["location"]


# --- User Story 4: privacy -------------------------------------------------------------


@pytest.mark.ac("016/AC-13")
async def test_only_my_own_entry_shows(
    member: httpx.AsyncClient, factory: Factory, w: dict[str, Any]
) -> None:
    bob = await factory.user("bob", display_name="Bob")
    await factory.entry(bob, w["gods"], status="finished", finished_on=date(2024, 2, 2),
                        notes="Bob's secret note", times_read=3)  # fmt: skip
    text = text_of((await member.get(f"/books/{w['gods']}")).text)
    assert "Not on my list" in text
    for leaked in ("Bob", "secret", "Finished", "2 Feb 2024", "Reading"):
        assert leaked not in text, leaked
    await factory.entry(bob, w["mort"], status="reading", notes="Bob's other note")
    mine = text_of((await member.get(f"/books/{w['mort']}")).text)
    assert "Finished" in mine and "Bob" not in mine  # my own status (Finished), not Bob's


# --- PR #37 review ---------------------------------------------------------------------


@pytest.mark.ac("016/AC-07")
async def test_author_page_story_books_open_the_book_page(
    member: httpx.AsyncClient, w: dict[str, Any]
) -> None:
    """The books named in an author page's Stories list, and on Edit story."""
    author = (await member.get(f"/authors/{w['terry']}")).text
    stories = author[author.find("<h2>Stories</h2>") :]
    assert f'<a href="/books/{w["tales"]}">Disc Tales</a>' in stories
    assert "/edit" not in stories.split("</ul>")[0]
    edit = (await member.get(f"/catalog/stories/{w['story']}/edit")).text
    assert link(edit, "Disc Tales") == f"/books/{w['tales']}"


@pytest.mark.ac("016/AC-04")
async def test_quick_notice_follows_my_reading(
    member: httpx.AsyncClient, w: dict[str, Any]
) -> None:
    """The contract's order: the notice comes after the My reading section."""
    response = await quick_add(member, w["gods"], f"/books/{w['gods']}")
    page = (await member.get(response.headers["location"])).text
    assert -1 < page.find('id="my-reading-heading"') < page.find('id="quick-notice"')


@pytest.mark.ac("016/AC-12")
async def test_only_story_notices_show(member: httpx.AsyncClient, w: dict[str, Any]) -> None:
    for code in ("removed", "added&stories=3", "saved", "reread"):
        page = text_of((await member.get(f"/books/{w['gods']}?msg={code}")).text)
        for wrong in ("Removed from your list", "Added to your list", "Saved.", "re-read"):
            assert wrong not in page, code
    page = text_of((await member.get(f"/books/{w['gods']}?msg=story_already")).text)
    assert "That story is already in this book." in page
