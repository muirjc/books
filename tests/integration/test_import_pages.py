"""The import pages (spec 002 user story 1; contracts/ui-routes.md; T027, T028, T043)."""

from __future__ import annotations

import re
from collections.abc import Callable

import httpx
import pytest

from tests.conftest import Factory, ui_csrf
from tests.fakes import FakeBookSource, author, listing, work
from tests.integration.import_helpers import KEY, confirm_via_page, member, stock


@pytest.mark.ac("002/AC-01")
async def test_search_page_for_any_member(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    _, client = await member(factory, client_factory, "kid")  # a Member, not an Admin (FR-014)
    page = await client.get("/import")
    assert page.status_code == 200
    assert 'name="q"' in page.text
    assert 'href="/import"' in page.text  # in the main navigation


async def test_single_match_goes_straight_to_the_works(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    plain = await client.get("/import/authors", params={"q": "Ann Author"})
    assert plain.status_code == 303 and plain.headers["location"] == f"/import/authors/{KEY}"
    htmx = await client.get("/import/authors", params={"q": "Ann Author"},
                            headers={"HX-Request": "true"})  # fmt: skip
    assert htmx.headers["HX-Redirect"] == f"/import/authors/{KEY}"


@pytest.mark.ac("002/AC-01")
@pytest.mark.ac("002/AC-04")
@pytest.mark.ac("002/AC-17")
@pytest.mark.ac("002/AC-19")
async def test_works_page_shows_states_and_status_choice(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    alice, client = await member(factory, client_factory, "alice")
    ann = await factory.author("Ann Author", alice)
    mine = await factory.book("Book 1", alice, author_ids=[ann])
    await factory.entry(alice, mine)
    await factory.book("Book 2", alice, author_ids=[ann])
    page = await client.get(f"/import/authors/{KEY}")
    assert page.status_code == 200
    text = page.text
    assert "Already on your list" in text and "In the family catalog" in text
    assert 'value="OL1W"' not in text  # no checkbox for a book on my list
    assert 'value="OL2W"' in text and 'value="OL3W"' in text
    assert '<option value="finished" selected>' in text


@pytest.mark.ac("002/AC-02")
async def test_confirm_shows_the_summary(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    done = await confirm_via_page(client, ["OL1W", "OL2W"])
    assert done.status_code == 200
    assert "Added 2 books to your list (2 new to the family catalog)" in done.text
    assert 'aria-live="polite"' in done.text


async def test_confirm_needs_csrf_and_a_selection(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    await client.get(f"/import/authors/{KEY}")
    forged = await client.post(
        f"/import/authors/{KEY}",
        data={"work": "OL1W", "status": "finished"},
        headers={"X-CSRF-Token": ""},
    )
    assert forged.status_code == 403
    token = await ui_csrf(client)
    empty = await client.post(
        f"/import/authors/{KEY}", data={"csrf_token": token, "status": "finished"},
        headers={"X-CSRF-Token": ""},
    )  # fmt: skip
    assert empty.status_code == 422
    assert "Tick at least one book" in empty.text
    assert await factory.scalar("SELECT count(*) FROM reading_entry") == 0


@pytest.mark.ac("002/AC-21")
async def test_more_than_500_on_the_page(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    book_source.works[KEY] = listing(KEY, [work(n) for n in range(1, 502)])
    _, client = await member(factory, client_factory, "alice")
    refused = await confirm_via_page(client, [f"OL{n}W" for n in range(1, 502)])
    assert refused.status_code == 422
    assert "You can add up to 500 books at a time" in refused.text


@pytest.mark.ac("002/AC-23")
async def test_unknown_author_page(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    _, client = await member(factory, client_factory, "alice")
    page = await client.get("/import/authors/OL999A")
    assert page.status_code == 404
    assert "No such author on Open Library" in page.text


async def test_known_author_with_no_works_page(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    """books-0tw.4: a real author Open Library lists no books for gets a 200 page saying
    so, with a way to add a book by hand, and no Add button."""
    book_source.works[KEY] = listing(KEY, [], name="Quiet Writer")
    _, client = await member(factory, client_factory, "alice")
    page = await client.get(f"/import/authors/{KEY}")
    assert page.status_code == 200
    assert "Books by Quiet Writer" in page.text
    assert "Open Library lists no books for this author." in page.text
    assert '<a href="/books/add">Add a book by hand</a>' in page.text
    assert "No books match" not in page.text
    assert "Add ticked books to my list" not in page.text


@pytest.mark.ac("002/AC-07")
async def test_imported_book_shows_its_source(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    await confirm_via_page(client, ["OL2W"])
    entry_id = await factory.scalar("SELECT id FROM reading_entry")
    book_id = await factory.scalar("SELECT book_id FROM reading_entry")
    link = 'href="https://openlibrary.org/works/OL2W"'
    entry = await client.get(f"/entries/{entry_id}")
    assert "Imported from Open Library" in entry.text and link in entry.text
    edit = await client.get(f"/catalog/books/{book_id}/edit")
    assert "Imported from Open Library" in edit.text and link in edit.text


_ = author  # re-exported helper used by other page tests


# --------------------------------------------------------------------------- user story 3


_WORK_INPUT = re.compile(r"<input [^>]*>")


def submitted(html: str) -> list[str]:
    """The work ids a browser would send from this HTML: ticked boxes and hidden fields."""
    keys: list[str] = []
    for tag in _WORK_INPUT.findall(html):
        if 'name="work"' not in tag:
            continue
        if 'type="hidden"' in tag or (
            tag.startswith('<input type="checkbox"') and " checked" in tag
        ):
            match = re.search(r'value="([^"]+)"', tag)
            assert match
            keys.append(match.group(1))
    return keys


async def _view(client: httpx.AsyncClient, **data: object) -> httpx.Response:
    token = await ui_csrf(client)
    return await client.post(
        f"/import/authors/{KEY}/view",
        data={"csrf_token": token, **data},
        headers={"HX-Request": "true", "X-CSRF-Token": ""},
    )


@pytest.mark.ac("002/AC-10")
@pytest.mark.ac("002/AC-11")
async def test_sort_filter_and_select_all_keep_ticks(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    book_source.works[KEY] = listing(KEY, [
        work(1, "Mist One", year=2003), work(2, "Mist Two", year=2001), work(3, "Other", year=2002),
    ])  # fmt: skip
    alice, client = await member(factory, client_factory, "alice")
    await client.get(f"/import/authors/{KEY}")

    fragment = await _view(client, sort="year", q="mist", work=["OL3W"])
    assert fragment.status_code == 200
    assert fragment.text.lstrip().startswith('<div id="import-works">')  # a fragment
    text = fragment.text
    assert text.index("Mist Two") < text.index("Mist One")  # year order
    assert "Other</label>" not in text  # filtered out, but still ticked
    assert submitted(text) == ["OL3W"]  # kept as a hidden field (review finding 2)
    selected = await _view(client, sort="year", q="mist", select="shown", work=submitted(text))
    assert 'value="OL1W" id="work-OL1W" checked' in selected.text
    assert 'value="OL2W" id="work-OL2W" checked' in selected.text
    assert sorted(submitted(selected.text)) == ["OL1W", "OL2W", "OL3W"]

    blank = await _view(client, sort="", q="")  # blank boxes mean "not given"
    assert blank.status_code == 200 and "Other</label>" in blank.text

    done = await confirm_via_page(client, submitted(selected.text))
    assert "Added 3 books" in done.text
    titles = await factory.scalar(
        "SELECT array_agg(b.title ORDER BY b.title) FROM reading_entry e "
        "JOIN book b ON b.id = e.book_id WHERE e.user_id = :u", u=alice.id,
    )  # fmt: skip
    assert titles == ["Mist One", "Mist Two", "Other"]


@pytest.mark.ac("002/AC-11")
async def test_select_all_ticks_at_most_500(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    book_source.works[KEY] = listing(KEY, [work(n) for n in range(1, 601)])
    _, client = await member(factory, client_factory, "alice")
    await client.get(f"/import/authors/{KEY}")
    selected = await _view(client, select="shown")
    assert selected.text.count(" checked>") == 500
    assert "Only the first 500 shown were ticked" in selected.text


@pytest.mark.ac("002/AC-20")
async def test_truncation_note(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    book_source.works[KEY] = listing(KEY, [work(n) for n in range(1, 2001)], total=2500)
    _, client = await member(factory, client_factory, "alice")
    page = await client.get(f"/import/authors/{KEY}")
    assert "Showing the first 2,000 of 2,500 works" in page.text
    assert "add it by hand" in page.text
    api = await client.get(f"/api/v1/import/authors/{KEY}/works")
    assert api.json()["truncated"] is True and api.json()["total"] == 2500


@pytest.mark.ac("002/AC-10")
async def test_enter_in_the_filter_applies_it_and_ticks_nothing(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    """The form's default button is "Apply sort and filter", not "Select all shown"."""
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    page = await client.get(f"/import/authors/{KEY}")
    form = page.text[page.text.index('id="import-form"') :]
    first_submit = re.search(r"<button [^>]*type=\"submit\"[^>]*>([^<]*)</button>", form)
    assert first_submit and first_submit.group(1) == "Apply sort and filter"
    assert 'name="select"' not in first_submit.group(0)


async def _expire_cache(factory: Factory) -> None:
    await factory.execute(
        "UPDATE source_lookup_cache SET fetched_at = fetched_at - interval '2 days', "
        "expires_at = expires_at - interval '2 days'"
    )


@pytest.mark.ac("002/AC-02")
async def test_confirm_after_the_results_expire(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    """No Open Library call under the import lock; the member gets a fresh list (finding 1)."""
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    await client.get(f"/import/authors/{KEY}")
    await _expire_cache(factory)
    calls = list(book_source.calls)
    token = await ui_csrf(client)
    sent = await client.post(
        f"/import/authors/{KEY}",
        data={"csrf_token": token, "status": "finished", "work": "OL1W"},
        headers={"X-CSRF-Token": ""},
    )
    assert sent.status_code == 303
    assert sent.headers["location"] == f"/import/authors/{KEY}?expired=1"
    assert book_source.calls == calls  # nothing fetched while confirming

    again = await client.get(sent.headers["location"])
    assert again.status_code == 200
    assert "The list had expired" in again.text
    assert book_source.calls == [*calls, ("author_works", KEY)]
    done = await confirm_via_page(client, ["OL1W"])  # the reload was kept, so this works
    assert "Added 1 book" in done.text


async def test_confirm_error_redisplays_from_the_cache(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    stock(book_source)
    _, client = await member(factory, client_factory, "alice")
    await client.get(f"/import/authors/{KEY}")
    calls = list(book_source.calls)
    token = await ui_csrf(client)
    sent = await client.post(
        f"/import/authors/{KEY}",
        content=str(
            httpx.QueryParams([("csrf_token", token), ("work", "OL1W"), ("work", "OL99W")])
        ),
        headers={"Content-Type": "application/x-www-form-urlencoded", "X-CSRF-Token": ""},
    )
    assert sent.status_code == 422
    assert "Some books aren" in sent.text
    assert 'value="OL1W" id="work-OL1W" checked' in sent.text  # ticks kept
    assert book_source.calls == calls


async def test_count_is_a_persistent_live_region(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    """books-0tw.3: the "N shown" line is announced from a live region that stays on the
    page; HTMX updates its text out of band instead of replacing it."""
    book_source.works[KEY] = listing(KEY, [work(1, "Mist One"), work(2, "Other")])
    _, client = await member(factory, client_factory, "alice")
    page = await client.get(f"/import/authors/{KEY}")
    region = re.search(
        r'<p aria-live="polite" class="muted" id="import-count">(.*?)</p>', page.text, re.S
    )
    assert region and "2 books shown." in " ".join(region.group(1).split())
    fragment_div = page.text.split('<div id="import-works">', 1)[1]
    assert page.text.index('id="import-count"') < page.text.index('<div id="import-works">')
    assert "aria-live" not in fragment_div.split("</form>", 1)[0]
    fragment = await _view(client, q="mist")
    assert "aria-live" not in fragment.text
    oob = re.search(r'<div hx-swap-oob="innerHTML:#import-count">(.*?)</div>', fragment.text, re.S)
    assert oob and "1 book shown." in " ".join(oob.group(1).split())
    assert fragment.text.rstrip().endswith("</div>")


async def test_ticks_hidden_by_the_filter_are_counted_and_fixable(
    factory: Factory, client_factory: Callable[[], httpx.AsyncClient], book_source: FakeBookSource
) -> None:
    """books-0tw.5: the count says how many ticks the filter hides and offers to show
    them; it counts only ids the form actually sends (not books already on my list)."""
    book_source.works[KEY] = listing(KEY, [
        work(1, "Mist One"), work(2, "Mist Two"), work(3, "Other"), work(4, "Another"),
    ])  # fmt: skip
    alice, client = await member(factory, client_factory, "alice")
    await client.get(f"/import/authors/{KEY}")
    await confirm_via_page(client, ["OL2W"])  # Mist Two is now on Alice's list
    fragment = await _view(client, q="mist", work=["OL2W", "OL3W", "OL4W", "OL1W"])
    sent = submitted(fragment.text)
    assert sorted(sent) == ["OL1W", "OL3W", "OL4W"]  # OL2W has no checkbox: not counted
    count = " ".join(
        re.sub(r"<[^>]+>", " ", fragment.text.split('innerHTML:#import-count">', 1)[1]).split()
    )
    assert count.startswith(f"2 books shown, {len(sent)} ticked (2 hidden by the filter).")
    clear = re.search(
        r'<button type="submit" formaction="/import/authors/OL1A/view" name="q" value="">'
        r"([^<]+)</button>",
        fragment.text,
    )
    assert clear and clear.group(1) == "Show all books"
    # Pressing it: the browser sends q="" after the filter box's value; ticks are kept.
    token = await ui_csrf(client)
    page = await client.post(
        f"/import/authors/{KEY}/view",
        content=f"csrf_token={token}&q=mist&work=OL1W&work=OL3W&work=OL4W&q=".encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert page.status_code == 200
    assert "Other</label>" in page.text and "Another</label>" in page.text
    assert 'id="filter" name="q" value=""' in page.text
    assert sorted(submitted(page.text)) == ["OL1W", "OL3W", "OL4W"]
    assert "hidden by the filter" not in page.text
