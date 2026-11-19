"""The import service with a fake Open Library (spec 002 user stories 1 and 3; T023, T040, T041)."""

from __future__ import annotations

import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from book_tracker.domain.enums import ReadingStatus
from book_tracker.domain.imports import SkipReason, WorkState
from book_tracker.persistence import source_cache
from book_tracker.services import imports
from book_tracker.services.errors import ConflictError, SourceNotFound, ValidationFailed
from tests.conftest import Factory, TestUser
from tests.fakes import FakeBookSource, author, listing, work

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
KEY = "OL1A"


@pytest.fixture
def ol() -> FakeBookSource:
    return FakeBookSource()


async def _list(app: Any, ol: FakeBookSource, user: TestUser, **kw: Any) -> Any:
    async with app.state.db.sessionmaker() as db:
        view = await imports.list_works(db, ol, user.id, KEY, kw.pop("now", NOW), **kw)
        await db.commit()
    return view


async def _confirm(app: Any, user: TestUser, keys: list[str], **kw: Any) -> Any:
    async with app.state.db.sessionmaker() as db:
        result = await imports.confirm_import(
            db,
            user.id,
            author_key=kw.pop("author_key", KEY),
            work_keys=keys,
            status=kw.pop("status", ReadingStatus.FINISHED),
            now=kw.pop("now", NOW),
        )
        await db.commit()
    return result


async def _states(app: Any, ol: FakeBookSource, user: TestUser) -> dict[str, WorkState]:
    view = await _list(app, ol, user)
    return {w.work.title: w.state for w in view.works}


# --------------------------------------------------------------------------- searching


@pytest.mark.ac("002/AC-01")
async def test_search_returns_candidates_and_is_cached(app: Any, ol: FakeBookSource) -> None:
    ol.authors["ann author"] = [author()]
    async with app.state.db.sessionmaker() as db:
        first = await imports.search_authors(db, ol, "  Ann   Author ", NOW)
        second = await imports.search_authors(db, ol, "ann author", NOW + timedelta(hours=1))
        await db.commit()
    assert [a.name for a in first] == ["Ann Author"] == [a.name for a in second]
    assert ol.calls == [("search_authors", "Ann Author")]  # the second came from the cache


@pytest.mark.ac("002/AC-01")
@pytest.mark.ac("002/AC-03")
async def test_listing_shows_works_and_writes_nothing(
    app: Any, ol: FakeBookSource, factory: Factory
) -> None:
    alice = await factory.user("alice")
    ol.works[KEY] = listing(KEY, [work(1, "First"), work(2, "Second", year=None)])
    view = await _list(app, ol, alice)
    assert [(w.work.title, w.state) for w in view.works] == [
        ("First", WorkState.NEW),
        ("Second", WorkState.NEW),
    ]
    assert view.author.name == "Ann Author"
    assert await factory.scalar("SELECT count(*) FROM book") == 0
    assert await factory.scalar("SELECT count(*) FROM reading_entry") == 0


@pytest.mark.ac("002/AC-04")
@pytest.mark.ac("002/AC-15")
@pytest.mark.ac("002/AC-17")
async def test_states_against_catalog_and_my_list(
    app: Any, ol: FakeBookSource, factory: Factory
) -> None:
    alice = await factory.user("alice")
    ann = await factory.author("Ann Author", alice)
    on_list = await factory.book("On My List", alice, author_ids=[ann])
    await factory.entry(alice, on_list)
    await factory.book("By Title", alice, author_ids=[ann])
    await factory.book("Something Else", alice, isbn_13="9780306406157")
    ol.works[KEY] = listing(KEY, [
        work(1, "On My List"), work(2, "The By Title"), work(3, "Isbn Match",
             isbns=frozenset({"9780306406157"})), work(4, "Brand New"),
    ])  # fmt: skip
    assert await _states(app, ol, alice) == {
        "On My List": WorkState.ON_MY_LIST,
        "The By Title": WorkState.IN_CATALOG,
        "Isbn Match": WorkState.IN_CATALOG,
        "Brand New": WorkState.NEW,
    }


async def test_alias_ids_match_source_refs(app: Any, ol: FakeBookSource, factory: Factory) -> None:
    alice = await factory.user("alice")
    ol.works[KEY] = listing(KEY, [work(1, "Merged")])
    await _list(app, ol, alice)
    await _confirm(app, alice, ["OL1W"])
    ben = await factory.user("ben")
    ol.works[KEY] = listing(KEY, [work(7, "Merged Again", aliases=("OL1W",))])
    await source_cache_clear(app)
    assert await _states(app, ol, ben) == {"Merged Again": WorkState.IN_CATALOG}


@pytest.mark.ac("002/AC-10")
async def test_sorting_by_title_and_year(app: Any, ol: FakeBookSource, factory: Factory) -> None:
    alice = await factory.user("alice")
    ol.works[KEY] = listing(KEY, [
        work(1, "Banana", year=2001), work(2, "The Apple", year=None), work(3, "Cherry", year=1999),
    ])  # fmt: skip
    by_title = await _list(app, ol, alice, sort="title")
    assert [w.work.title for w in by_title.works] == ["The Apple", "Banana", "Cherry"]
    by_year = await _list(app, ol, alice, sort="year")
    assert [w.work.title for w in by_year.works] == ["Cherry", "Banana", "The Apple"]


@pytest.mark.ac("002/AC-23")
async def test_unknown_author_key(app: Any, ol: FakeBookSource, factory: Factory) -> None:
    alice = await factory.user("alice")
    with pytest.raises(SourceNotFound):
        await _list(app, ol, alice)


async def test_near_expiry_cache_is_refreshed(
    app: Any, ol: FakeBookSource, factory: Factory
) -> None:
    alice = await factory.user("alice")
    ol.works[KEY] = listing(KEY, [work(1, "Old")])
    await _list(app, ol, alice)
    ol.works[KEY] = listing(KEY, [work(1, "Old"), work(2, "Newer")])
    soon = NOW + timedelta(hours=23, minutes=30)  # under an hour left (research R8)
    view = await _list(app, ol, alice, now=soon)
    assert [w.work.title for w in view.works] == ["Newer", "Old"]  # refetched; title order
    assert view.fetched_at == soon


# --------------------------------------------------------------------------- confirming


@pytest.mark.ac("002/AC-02")
@pytest.mark.ac("002/AC-07")
@pytest.mark.ac("002/AC-14")
@pytest.mark.ac("002/AC-19")
async def test_confirm_adds_selected_books_with_provenance(
    app: Any, ol: FakeBookSource, factory: Factory
) -> None:
    alice = await factory.user("alice")
    ol.works[KEY] = listing(KEY, [work(1, "One"), work(2, "Two"), work(3, "Three")])
    await _list(app, ol, alice)
    result = await _confirm(app, alice, ["OL1W", "OL3W"])
    assert sorted(b.title for b in result.added) == ["One", "Three"]
    assert all(b.new_to_catalog for b in result.added)
    assert result.skipped == ()
    rows = await factory.scalar(
        "SELECT json_agg(json_build_object('title', b.title, 'series', b.series_id, "
        "'isbn', b.isbn_13, 'created_by', b.created_by, 'work', r.source_work_id, "
        "'source', r.source, 'by', r.imported_by, 'status', e.status, 'times', e.times_read)) "
        "FROM book b JOIN book_source_ref r ON r.book_id = b.id "
        "JOIN reading_entry e ON e.book_id = b.id AND e.user_id = :u",
        u=alice.id,
    )
    assert len(rows) == 2
    for row in rows:
        assert row["series"] is None and row["isbn"] is None  # AC-14
        assert row["created_by"] == str(alice.id) == row["by"]  # AC-07
        assert row["source"] == "open_library" and row["work"] in {"OL1W", "OL3W"}
        assert row["status"] == "finished" and row["times"] == 1  # AC-19 default


@pytest.mark.ac("002/AC-19")
async def test_chosen_status_applies_to_all(app: Any, ol: FakeBookSource, factory: Factory) -> None:
    alice = await factory.user("alice")
    ol.works[KEY] = listing(KEY, [work(1), work(2)])
    await _list(app, ol, alice)
    await _confirm(app, alice, ["OL1W", "OL2W"], status=ReadingStatus.WANT_TO_READ)
    statuses = await factory.scalar("SELECT array_agg(DISTINCT status) FROM reading_entry")
    assert statuses == ["want_to_read"]
    assert await factory.scalar("SELECT max(times_read) FROM reading_entry") == 0


@pytest.mark.ac("002/AC-05")
@pytest.mark.ac("002/AC-06")
async def test_authors_are_reused_and_co_authors_kept_in_order(
    app: Any, ol: FakeBookSource, factory: Factory
) -> None:
    alice = await factory.user("alice")
    existing = await factory.author("ANN AUTHOR", alice)
    ol.works[KEY] = listing(KEY, [work(1, "Together", ("Ann Author", "Bea Writer"))])
    await _list(app, ol, alice)
    await _confirm(app, alice, ["OL1W"])
    assert await factory.scalar("SELECT count(*) FROM author") == 2
    order = await factory.scalar(
        "SELECT array_agg(a.name ORDER BY ba.position) FROM book_author ba "
        "JOIN author a ON a.id = ba.author_id"
    )
    assert order == ["ANN AUTHOR", "Bea Writer"]
    assert await factory.scalar("SELECT author_id FROM book_author WHERE position = 1") == existing


@pytest.mark.ac("002/AC-05")
async def test_author_matched_across_unicode_forms(
    app: Any, ol: FakeBookSource, factory: Factory
) -> None:
    alice = await factory.user("alice")
    await factory.author(unicodedata.normalize("NFD", "José Saramago"), alice)
    ol.works[KEY] = listing(KEY, [work(1, "Blindness", ("José Saramago",))], name="José Saramago")
    await _list(app, ol, alice)
    await _confirm(app, alice, ["OL1W"])
    assert await factory.scalar("SELECT count(*) FROM author") == 1


@pytest.mark.ac("002/AC-04")
async def test_catalog_book_is_added_to_my_list_without_a_copy(
    app: Any, ol: FakeBookSource, factory: Factory
) -> None:
    alice, ben = await factory.user("alice"), await factory.user("ben")
    ann = await factory.author("Ann Author", alice)
    await factory.book("Shared", alice, author_ids=[ann])
    ol.works[KEY] = listing(KEY, [work(1, "Shared")])
    await _list(app, ol, ben)
    result = await _confirm(app, ben, ["OL1W"])
    assert [(b.title, b.new_to_catalog) for b in result.added] == [("Shared", False)]
    assert await factory.scalar("SELECT count(*) FROM book") == 1


@pytest.mark.ac("002/AC-17")
async def test_books_already_on_my_list_are_skipped(
    app: Any, ol: FakeBookSource, factory: Factory
) -> None:
    alice = await factory.user("alice")
    ol.works[KEY] = listing(KEY, [work(1, "Mine"), work(2, "New")])
    await _list(app, ol, alice)
    await _confirm(app, alice, ["OL1W"])
    again = await _confirm(app, alice, ["OL1W", "OL2W"])
    assert [b.title for b in again.added] == ["New"]
    assert [(s.title, s.reason) for s in again.skipped] == [("Mine", SkipReason.ON_LIST)]
    assert await factory.scalar("SELECT count(*) FROM reading_entry") == 2


@pytest.mark.ac("002/AC-22")
async def test_two_works_for_one_catalog_book(
    app: Any, ol: FakeBookSource, factory: Factory
) -> None:
    alice = await factory.user("alice")
    await factory.book("Catalogued", alice, isbn_13="9780306406157")
    isbn = frozenset({"9780306406157"})
    ol.works[KEY] = listing(KEY, [
        work(1, "Edition One", isbns=isbn), work(2, "Edition Two", isbns=isbn), work(3, "Other"),
    ])  # fmt: skip
    await _list(app, ol, alice)
    result = await _confirm(app, alice, ["OL1W", "OL2W", "OL3W"])
    assert sorted(b.title for b in result.added) == ["Edition One", "Other"]
    assert [(s.title, s.reason) for s in result.skipped] == [("Edition Two", SkipReason.DUPLICATE)]


@pytest.mark.ac("002/AC-22")
async def test_author_listed_twice_is_added_once(
    app: Any, ol: FakeBookSource, factory: Factory
) -> None:
    alice = await factory.user("alice")
    ol.works[KEY] = listing(KEY, [work(1, "Twice", ("Ann Author", "ann author"))])
    await _list(app, ol, alice)
    result = await _confirm(app, alice, ["OL1W"])
    assert len(result.added) == 1
    assert await factory.scalar("SELECT count(*) FROM book_author") == 1


@pytest.mark.ac("002/AC-21")
async def test_more_than_500_is_refused(app: Any, ol: FakeBookSource, factory: Factory) -> None:
    alice = await factory.user("alice")
    ol.works[KEY] = listing(KEY, [work(n) for n in range(1, 502)])
    await _list(app, ol, alice)
    with pytest.raises(ValidationFailed) as excinfo:
        await _confirm(app, alice, [f"OL{n}W" for n in range(1, 502)])
    assert "500" in excinfo.value.errors[0].message
    assert await factory.scalar("SELECT count(*) FROM book") == 0


async def test_expired_results_are_refused(app: Any, ol: FakeBookSource, factory: Factory) -> None:
    alice = await factory.user("alice")
    ol.works[KEY] = listing(KEY, [work(1)])
    await _list(app, ol, alice)
    with pytest.raises(ConflictError) as excinfo:
        await _confirm(app, alice, ["OL1W"], now=NOW + timedelta(hours=25))
    assert excinfo.value.code == "results_expired"


async def test_unknown_work_key_is_refused(app: Any, ol: FakeBookSource, factory: Factory) -> None:
    alice = await factory.user("alice")
    ol.works[KEY] = listing(KEY, [work(1)])
    await _list(app, ol, alice)
    with pytest.raises(ValidationFailed):
        await _confirm(app, alice, ["OL999W"])


async def test_long_title_is_stored_cut_to_fit(
    app: Any, ol: FakeBookSource, factory: Factory
) -> None:
    """FR-022: the adapter cuts titles; the service stores them as given."""
    alice = await factory.user("alice")
    title = ("Long " * 59).strip() + "…"  # what the adapter produces
    ol.works[KEY] = listing(KEY, [work(1, title)])
    await _list(app, ol, alice)
    await _confirm(app, alice, ["OL1W"])
    stored = await factory.scalar("SELECT title FROM book")
    assert stored == title and len(stored) <= 300


async def source_cache_clear(app: Any) -> None:
    async with app.state.db.sessionmaker() as db:
        await db.execute(source_cache.models.SourceLookupCache.__table__.delete())
        await db.commit()


_ = uuid  # used in type positions by other tests in this module
