"""Spec 013 T002: story rows on Add a book, parsed and checked before anything is saved."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from starlette.datastructures import FormData

from book_tracker.web.forms import MAX_STORY_ROWS, parse_add_book

BOOK = [("title", "Side Jobs"), ("author_name_0", "Jim Butcher"), ("series_name", "Dresden")]


def parse(*pairs: tuple[str, str], book: list[tuple[str, str]] = BOOK, tick: bool = True):  # type: ignore[no-untyped-def]
    items = list(book) + ([("anthology", "yes")] if tick else []) + list(pairs)
    return parse_add_book(FormData(items))


def test_no_anthology_no_rows() -> None:
    form = parse_add_book(FormData(BOOK))
    assert form.anthology is False and form.stories == []
    assert not form.errors


@pytest.mark.ac("013/AC-02")
def test_ticked_without_rows_gives_one_blank_row() -> None:
    form = parse()
    assert form.anthology is True
    assert len(form.stories) == 1 and form.stories[0].is_blank
    assert not form.errors  # AC-07: blank rows are not errors


@pytest.mark.ac("013/AC-03")
def test_rows_are_read_in_order_and_renumbered() -> None:
    form = parse(
        ("story_title_4", "Something Borrowed"), ("story_number_4", "6.5"),
        ("story_title_0", "Restoration of Faith"), ("story_number_0", "1.5"),
        ("story_title_2", "Publicity"), ("story_number_2", "2.5"),
        ("story_author_name_2", "  Jim   Butcher "), ("story_series_name_2", " Other  Series"),
    )  # fmt: skip
    assert [row.title for row in form.stories] == [
        "Restoration of Faith", "Publicity", "Something Borrowed",
    ]  # fmt: skip
    assert [row.index for row in form.stories] == [0, 1, 2]
    assert form.stories[1].number == Decimal("2.5")
    assert form.stories[1].author_name == "Jim Butcher"
    assert form.stories[1].series_name == "Other Series"
    assert not form.errors


@pytest.mark.ac("013/AC-06")
def test_rows_past_the_limit_are_dropped() -> None:
    pairs = [(f"story_title_{i}", f"S{i}") for i in range(MAX_STORY_ROWS + 5)]
    pairs += [(f"story_number_{i}", str(i)) for i in range(MAX_STORY_ROWS + 5)]
    assert MAX_STORY_ROWS == 50
    assert len(parse(*pairs).stories) == 50


@pytest.mark.ac("013/AC-07")
def test_blank_rows_are_ignored() -> None:
    form = parse(("story_title_0", ""), ("story_number_0", ""), ("story_title_1", "A"),
                 ("story_number_1", "1.5"))  # fmt: skip
    assert form.stories[0].is_blank and not form.stories[1].is_blank
    assert [row.title for row in form.filled_stories] == ["A"]
    assert not form.errors


@pytest.mark.ac("013/AC-10")
@pytest.mark.parametrize(
    ("pairs", "field", "message"),
    [
        ((("story_number_0", "1.5"),), "story_title_0", "Story 1: Enter the story's title"),
        ((("story_title_0", "A"),), "story_number_0", "Story 1: Enter the story's number"),
        ((("story_title_0", "A"), ("story_number_0", "1000")), "story_number_0", "Story 1: "),
        ((("story_title_0", "A"), ("story_number_0", "x")), "story_number_0", "Story 1: "),
        ((("story_title_0", "A" * 301), ("story_number_0", "1")), "story_title_0", "Story 1: Keep"),
        ((("story_author_name_0", "Ann"),), "story_title_0", "Story 1: Enter"),
    ],
)
def test_row_field_errors(pairs: tuple[tuple[str, str], ...], field: str, message: str) -> None:
    form = parse(*pairs)
    assert form.errors[field].startswith(message), form.errors
    assert form.field_errors


@pytest.mark.ac("013/AC-11")
def test_no_series_anywhere() -> None:
    book = [("title", "Side Jobs"), ("author_name_0", "Jim Butcher")]
    form = parse(("story_title_0", "A"), ("story_number_0", "1.5"), book=book)
    assert form.errors["story_series_name_0"] == (
        "Story 1: Choose a series for this story, or give the book a series"
    )
    ok = parse(("story_title_0", "A"), ("story_number_0", "1.5"),
               ("story_series_name_0", "Dresden"), book=book)  # fmt: skip
    assert not ok.errors


@pytest.mark.ac("013/AC-12")
def test_repeated_series_and_number() -> None:
    form = parse(
        ("story_title_0", "A"), ("story_number_0", "2.5"),
        ("story_title_1", "B"), ("story_number_1", "3.5"),
        ("story_title_2", "C"), ("story_number_2", "2.50"), ("story_series_name_2", "dresden"),
    )  # fmt: skip
    message = "Story 1 and Story 3 have the same number in Dresden"
    assert form.errors["story_number_0"] == message
    assert form.errors["story_number_2"] == message
    assert "story_number_1" not in form.errors
    other = parse(("story_title_0", "A"), ("story_number_0", "2.5"),
                  ("story_title_1", "B"), ("story_number_1", "2.5"),
                  ("story_series_name_1", "Other"))  # fmt: skip
    assert not other.errors  # different series


@pytest.mark.ac("013/AC-08")
def test_unticked_box_with_text_in_rows() -> None:
    form = parse(("story_title_0", "A"), tick=False)
    assert form.anthology is False
    assert form.errors["anthology"].startswith("Tick “This book is an anthology or collection”")
    assert not parse(("story_title_0", ""), tick=False).errors  # empty rows are fine


@pytest.mark.ac("013/AC-13")
def test_existing_story_row() -> None:
    story = uuid.uuid4()
    form = parse(("story_id_0", str(story)), ("story_title_0", "Publicity"),
                 ("story_number_0", "2.5"), ("story_series_name_0", "Dresden"),
                 ("story_id_1", "not-a-uuid"), ("story_title_1", "B"),
                 ("story_number_1", "3"))  # fmt: skip
    assert form.stories[0].story_id == story and not form.stories[0].is_blank
    assert form.stories[1].story_id is None
    assert not form.errors


@pytest.mark.ac("013/AC-18")
def test_a_chosen_book_has_no_stories() -> None:
    form = parse_add_book(FormData([("book_id", str(uuid.uuid4())), ("anthology", "yes"),
                                    ("story_title_0", "A")]))  # fmt: skip
    assert form.anthology is False and form.stories == [] and not form.errors


def test_name_answers_are_read_per_row() -> None:
    robb = uuid.uuid4()
    form = parse(("story_title_0", "A"), ("story_number_0", "1"),
                 ("story_author_name_0", "J DM Robb"), ("confirm_story_author_0", " J DM Robb"),
                 ("story_series_name_0", "In Deth"), ("use_story_series_0", str(robb)),
                 ("story_author_id_0", "bad"), ("story_series_id_0", str(robb)))  # fmt: skip
    row = form.stories[0]
    assert row.author_confirmed == "J DM Robb" and row.use_series_id == robb
    assert row.author_id is None and row.series_id == robb


def test_non_ascii_digits_in_field_names_are_ignored() -> None:
    """PR #33 review: "²".isdigit() is True but int("²") fails."""
    form = parse(("story_title_²", "x"), ("story_title_0", "A"), ("story_number_0", "1"))
    assert [row.title for row in form.stories] == ["A"]


@pytest.mark.ac("013/AC-10")
def test_long_author_and_series_names_are_refused() -> None:
    """PR #33 review: names over 200 characters were a database error (500)."""
    form = parse(
        ("story_title_0", "A"), ("story_number_0", "1"),
        ("story_author_name_0", "A" * 201), ("story_series_name_0", "S" * 201),
    )  # fmt: skip
    assert form.errors["story_author_name_0"] == "Story 1: Keep the name to 200 characters or fewer"
    assert form.errors["story_series_name_0"] == "Story 1: Keep the name to 200 characters or fewer"
    book = parse_add_book(FormData([("title", "T"), ("author_name_0", "A" * 201),
                                    ("series_name", "S" * 201)]))  # fmt: skip
    assert book.errors["author_name_0"] == "Keep the name to 200 characters or fewer"
    assert book.errors["series_name"] == "Keep the name to 200 characters or fewer"


def test_the_story_forms_keep_their_picked_story() -> None:
    """PR #33 review: the spec 009 Add story form's ``story_id`` survived a redraw."""
    from book_tracker.web.forms import parse_story

    story = str(uuid.uuid4())
    form, picked, _ = parse_story(FormData([("title", "A"), ("story_id", story)]))
    assert picked == uuid.UUID(story) and form.raw["story_id"] == story
