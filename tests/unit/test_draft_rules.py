"""Spec 012 research R4–R6: the rules a draft must pass, its cache key and the saved origin."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from book_tracker.domain.drafts import (
    BLOCKED_DOMAINS,
    DRAFT_TTL,
    StoredDraft,
    copies_source,
    draft_key,
    is_blocked,
    keep_sources,
    origin_for,
    word_count,
)

NOW = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


def test_draft_key_prefers_isbn() -> None:
    assert draft_key("9780451457813", "Storm Front", ["Jim Butcher"]) == "isbn:9780451457813"


@pytest.mark.ac("012/AC-15")
def test_draft_key_by_title_and_authors_is_normalized() -> None:
    one = draft_key(None, "The  Storm Front!", ["Jim Butcher", "Ann Other"])
    two = draft_key(None, "storm front", ["ANN OTHER", " jim  butcher"])
    assert one == two
    assert one.startswith("ta:")
    assert draft_key(None, "Storm Front", ["Jim Butcher"]) != one  # authors differ


@pytest.mark.ac("012/AC-17")
def test_draft_key_changes_with_details() -> None:
    base = draft_key(None, "Storm Front", ["Jim Butcher"])
    assert draft_key(None, "Fool Moon", ["Jim Butcher"]) != base
    assert draft_key("9780451457813", "Storm Front", ["Jim Butcher"]) != base


@pytest.mark.ac("012/AC-12")
def test_word_count() -> None:
    assert word_count("") == 0
    assert word_count("One two  three\nfour — five") == 5
    assert word_count("Harry's world-weary voice") == 3


@pytest.mark.ac("012/AC-13")
def test_copies_source_finds_twelve_word_runs() -> None:
    blurb = (
        "Harry Dresden is the best at what he does. Well, technically he's the only at "
        "what he does. So when the Chicago P.D. has a case that transcends mortal creativity"
    )
    copied = (
        "In this novel, HARRY DRESDEN is the best at what he does; well, technically, "
        "he's the only one."
    )
    assert copies_source(copied, blurb)  # 12 words in a row, case and punctuation aside
    own = "Chicago's only wizard for hire, Harry Dresden, takes a case for the police."
    assert not copies_source(own, blurb)
    twelve = "Harry Dresden is the best at what he does well technically he's"
    assert copies_source(twelve + " the", blurb)
    assert not copies_source("x " + " ".join(twelve.split()[:11]), blurb)
    assert not copies_source(copied, None)


@pytest.mark.ac("012/AC-11")
@pytest.mark.parametrize(
    "url",
    [
        "https://www.amazon.com/dp/0451457811",
        "https://amazon.co.uk/x",
        "http://smile.amazon.de/x",
        "https://www.goodreads.com/book/show/47212",
        "https://GOODREADS.com/x",
        "https://images.amazon.ca/x",
    ],
)
def test_blocked_sites(url: str) -> None:
    assert is_blocked(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://en.wikipedia.org/wiki/Storm_Front_(novel)",
        "https://notamazon.com/x",
        "https://goodreadsfan.com/x",
        "https://example.com/amazon.com",
        "not a url",
    ],
)
def test_allowed_sites(url: str) -> None:
    assert not is_blocked(url)


def test_blocked_domains_list_for_the_search_tool() -> None:
    assert "goodreads.com" in BLOCKED_DOMAINS and "amazon.com" in BLOCKED_DOMAINS
    assert all("://" not in d for d in BLOCKED_DOMAINS)


def test_keep_sources_only_known_urls() -> None:
    known = {"https://a.example/1", "https://b.example/2"}
    listed = ["https://b.example/2", "https://made.up/3", "https://b.example/2"]
    assert keep_sources(listed, known, cited=()) == ("https://b.example/2",)
    # Nothing listed: the cited pages are the sources.
    assert keep_sources([], known, cited=("https://a.example/1",)) == ("https://a.example/1",)
    many = [f"https://x.example/{n}" for n in range(30)]
    assert len(keep_sources(many, set(many), cited=())) == 20
    long = "https://x.example/" + "a" * 2100
    assert keep_sources([long], {long}, cited=()) == ()


def _draft(**changes: object) -> StoredDraft:
    values: dict[str, object] = {
        "draft_key": "isbn:9780451457813",
        "text": "A wizard  for hire.\n",
        "created_at": NOW - timedelta(days=1),
    }
    values.update(changes)
    return StoredDraft(**values)  # type: ignore[arg-type]  # test values are the right types


@pytest.mark.ac("012/AC-04")
def test_origin_ai_or_edited() -> None:
    key = "isbn:9780451457813"
    assert origin_for(_draft(), key, "  A wizard for hire. ", NOW) == "ai"
    assert origin_for(_draft(), key, "A wizard for hire, mostly.", NOW) == "ai_edited"


@pytest.mark.ac("012/AC-08")
def test_origin_manual_without_a_valid_draft() -> None:
    key = "isbn:9780451457813"
    assert origin_for(None, key, "text", NOW) == "manual"
    assert origin_for(_draft(draft_key="isbn:9780000000002"), key, "A wizard for hire.", NOW) == (
        "manual"
    )
    expired = _draft(created_at=NOW - DRAFT_TTL - timedelta(seconds=1))
    assert origin_for(expired, key, "A wizard for hire.", NOW) == "manual"
