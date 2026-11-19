"""Matching rules for imported works (research R6; task T008)."""

from __future__ import annotations

import unicodedata

import pytest

from book_tracker.domain.imports import WorkCandidate
from book_tracker.domain.matching import (
    clean,
    fit,
    isbn10_to_13,
    merge_duplicate_works,
    normalize_person_name,
    normalize_title,
    to_isbn13,
)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("The Way of Kings", "way of kings"),
        ("A Wizard of Earthsea", "wizard of earthsea"),
        ("Mistborn: The Final Empire", "mistborn the final empire"),
        ("  Elantris  ", "Elantris"),
        ("An Echo of Things to Come", "echo of things to come"),
    ],
)
def test_normalize_title_equal(a: str, b: str) -> None:
    assert normalize_title(a) == normalize_title(b)


@pytest.mark.parametrize("title", ["Anathem", "Theory of Everything", "Away"])
def test_leading_article_dropped_only_as_whole_word(title: str) -> None:
    assert normalize_title(title) == title.lower()


def test_normalize_title_unicode_forms() -> None:
    composed = "Les Misérables"
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed
    assert normalize_title(composed) == normalize_title(decomposed)


def test_normalize_person_name() -> None:
    assert normalize_person_name("  Ursula  K. Le Guin ") == "ursula k. le guin"
    assert normalize_person_name(unicodedata.normalize("NFD", "José")) == "josé"


def test_isbn10_to_13() -> None:
    assert isbn10_to_13("0765326353") == "9780765326355"
    assert isbn10_to_13("080442957X") == "9780804429573"
    assert isbn10_to_13("0765326354") is None  # bad check digit
    assert isbn10_to_13("12345") is None


def test_to_isbn13_accepts_valid_13_and_converts_10() -> None:
    assert to_isbn13("9780765326355") == "9780765326355"
    assert to_isbn13("0765326353") == "9780765326355"
    assert to_isbn13("9780765326356") is None  # bad check digit
    assert to_isbn13("not an isbn") is None


def test_fit_cuts_at_a_word_boundary_with_ellipsis() -> None:
    long = "word " * 100
    cut = fit(long, 300)
    assert len(cut) <= 300
    assert cut.endswith("…")
    assert not cut[:-1].endswith(" ")
    assert fit("Short", 300) == "Short"
    assert fit(unicodedata.normalize("NFD", "Café"), 300) == "Café"  # stored NFKC


def _work(work_id: str, title: str, author: str, year: int | None, editions: int,
          isbns: frozenset[str] = frozenset()) -> WorkCandidate:  # fmt: skip
    return WorkCandidate(
        source_id=work_id,
        alias_ids=(),
        title=title,
        first_publish_year=year,
        author_names=(author,),
        isbn13s=isbns,
        edition_count=editions,
    )


def test_merge_duplicate_works() -> None:
    works = [
        _work("OL1W", "The Final Empire", "Brandon Sanderson", 2006, 10, frozenset({"9780765311"})),
        _work("OL2W", "Final Empire", "brandon sanderson", 2001, 45, frozenset({"9780765350"})),
        _work("OL3W", "Elantris", "Brandon Sanderson", 2005, 30),
    ]  # fmt: skip
    merged = merge_duplicate_works(works)
    assert [w.source_id for w in merged] == ["OL2W", "OL3W"]
    final_empire = merged[0]
    assert final_empire.alias_ids == ("OL1W",)
    assert final_empire.first_publish_year == 2001
    assert final_empire.isbn13s == frozenset({"9780765311", "9780765350"})
    assert final_empire.edition_count == 45


def test_merge_keeps_different_first_authors_apart() -> None:
    works = [_work("OL1W", "Untitled", "A", 2000, 1), _work("OL2W", "Untitled", "B", 2000, 1)]
    assert len(merge_duplicate_works(works)) == 2


def test_clean_drops_control_characters() -> None:
    """PostgreSQL text and JSONB refuse NUL (second review, finding 3)."""
    assert clean("ann\x00 author\x07") == "ann author"
    assert clean("tab\tand\nnewline") == "tab and newline"
    assert "\x00" not in fit("a\x00b", 10)
