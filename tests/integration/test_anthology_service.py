"""Spec 013 T004: add_entry with stories, for the form and the API alike."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest

from book_tracker.services import catalog as catalog_service
from book_tracker.services import readings as service
from book_tracker.services.errors import StoryNumberTaken, ValidationFailed
from tests.conftest import Factory


async def _counts(factory: Factory) -> tuple[int, int, int, int]:
    return (
        await factory.scalar("SELECT count(*) FROM book"),
        await factory.scalar("SELECT count(*) FROM story"),
        await factory.scalar("SELECT count(*) FROM book_story"),
        await factory.scalar("SELECT count(*) FROM reading_entry"),
    )


@pytest.fixture
async def world(factory: Factory) -> dict[str, Any]:
    alice = await factory.user("alice")
    jim = await factory.author("Jim Butcher", alice)
    ann = await factory.author("Ann Other", alice)
    dresden = await factory.series("The Dresden Files", alice)
    other = await factory.series("Other Series", alice)
    return {"alice": alice, "jim": jim, "ann": ann, "dresden": dresden, "other": other}


def side_jobs(w: dict[str, Any], series: bool = True) -> catalog_service.NewBook:
    return catalog_service.NewBook(
        title="Side Jobs", author_ids=[w["jim"]], series_id=w["dresden"] if series else None
    )


async def _add(app: Any, w: dict[str, Any], stories: list[Any], *, series: bool = True) -> Any:
    async with app.state.db.sessionmaker() as db:
        try:
            entry = await service.add_entry(
                db, w["alice"].id, new_book=side_jobs(w, series), stories=stories
            )
        except BaseException:
            await db.rollback()
            raise
        await db.commit()
        return entry


@pytest.mark.ac("013/AC-03")
async def test_new_stories_default_to_the_books_series_and_authors(
    app: Any, factory: Factory, world: dict[str, Any]
) -> None:
    entry = await _add(app, world, [
        catalog_service.StoryForBook(title="Restoration of Faith", series_number=Decimal("1.5")),
        catalog_service.StoryForBook(
            title="Other Tale", series_number=Decimal("1"), series_id=world["other"],
            author_ids=[world["ann"]],
        ),
    ])  # fmt: skip
    async with app.state.db.sessionmaker() as db:
        stories = await catalog_service.book_stories(db, entry.book.id)
    by_title = {s.title: s for s in stories}
    faith = by_title["Restoration of Faith"]
    assert faith.series.id == world["dresden"] and faith.series_number == Decimal("1.5")
    assert [a.id for a in faith.authors] == [world["jim"]]
    other = by_title["Other Tale"]
    assert other.series.id == world["other"] and [a.id for a in other.authors] == [world["ann"]]


@pytest.mark.ac("013/AC-13")
async def test_an_existing_story_is_linked_not_copied(
    app: Any, factory: Factory, world: dict[str, Any]
) -> None:
    first = await factory.book("First Collection", world["alice"], author_ids=[world["jim"]])
    story = await factory.story(
        "Publicity", world["alice"], series_id=world["dresden"], series_number="2.5",
        author_ids=[world["jim"]], book_ids=[first],
    )  # fmt: skip
    entry = await _add(app, world, [catalog_service.StoryForBook(story_id=story)])
    assert await factory.scalar("SELECT count(*) FROM story") == 1
    assert await factory.scalar("SELECT count(*) FROM book_story WHERE story_id = :s", s=story) == 2
    assert entry.book.title == "Side Jobs"


@pytest.mark.ac("013/AC-16")
@pytest.mark.ac("013/AC-17")
async def test_a_taken_number_names_the_item_and_saves_nothing(
    app: Any, factory: Factory, world: dict[str, Any]
) -> None:
    first = await factory.book("First Collection", world["alice"], author_ids=[world["jim"]])
    story = await factory.story(
        "Publicity", world["alice"], series_id=world["dresden"], series_number="2.5",
        author_ids=[world["jim"]], book_ids=[first],
    )  # fmt: skip
    before = await _counts(factory)
    with pytest.raises(StoryNumberTaken) as caught:
        await _add(app, world, [
            catalog_service.StoryForBook(title="A", series_number=Decimal("1.5")),
            catalog_service.StoryForBook(title="B", series_number=Decimal("2.5")),
        ])  # fmt: skip
    assert caught.value.index == 1 and caught.value.story.id == story
    assert caught.value.code == "story_number_taken" and caught.value.existing_id == story
    assert await _counts(factory) == before


async def test_a_deleted_story_id(app: Any, factory: Factory, world: dict[str, Any]) -> None:
    before = await _counts(factory)
    with pytest.raises(ValidationFailed) as caught:
        await _add(app, world, [
            catalog_service.StoryForBook(title="A", series_number=Decimal("1")),
            catalog_service.StoryForBook(story_id=uuid.uuid4()),
        ])  # fmt: skip
    assert [e.field for e in caught.value.errors] == ["stories.1.story_id"]
    assert await _counts(factory) == before


@pytest.mark.ac("013/AC-11")
async def test_no_series_for_a_story(app: Any, factory: Factory, world: dict[str, Any]) -> None:
    with pytest.raises(ValidationFailed) as caught:
        item = catalog_service.StoryForBook(title="A", series_number=Decimal("1"))
        await _add(app, world, [item], series=False)
    assert [e.field for e in caught.value.errors] == ["stories.0.series_id"]
    assert await factory.scalar("SELECT count(*) FROM book") == 0


async def test_a_missing_series_or_author_names_the_item(
    app: Any, factory: Factory, world: dict[str, Any]
) -> None:
    with pytest.raises(ValidationFailed) as caught:
        await _add(app, world, [catalog_service.StoryForBook(
            title="A", series_number=Decimal("1"), series_id=uuid.uuid4(),
            author_ids=[uuid.uuid4()],
        )])  # fmt: skip
    assert sorted(e.field for e in caught.value.errors) == [
        "stories.0.author_ids", "stories.0.series_id",
    ]  # fmt: skip


@pytest.mark.ac("013/AC-26")
async def test_stories_need_a_new_book(app: Any, factory: Factory, world: dict[str, Any]) -> None:
    book = await factory.book("Existing", world["alice"])
    async with app.state.db.sessionmaker() as db:
        with pytest.raises(ValidationFailed) as caught:
            await service.add_entry(
                db, world["alice"].id, book_id=book,
                stories=[catalog_service.StoryForBook(title="A", series_number=Decimal("1"))],
            )  # fmt: skip
    assert [e.field for e in caught.value.errors] == ["stories"]
