"""Spec 005: finding catalog names similar to a typed one (research R3)."""

from __future__ import annotations

import uuid

import pytest

from book_tracker.domain.values import loose_name_key, similar_names

AUTHORS = [
    ("J.D. Robb", "Nora Roberts"), ("Nora Roberts", None), ("Jim Butcher", None),
    ("Terry Pratchett", None), ("Neil Gaiman", None), ("Ursula K. Le Guin", None),
    ("Brandon Sanderson", None), ("Robin Hobb", None), ("J.R.R. Tolkien", None),
    ("Agatha Christie", None), ("Stephen King", None), ("Lee Child", None),
    ("Robert Jordan", None),
]  # fmt: skip
SERIES = ["The Dresden Files", "Discworld", "The Wheel of Time", "Earthsea", "In Death",
          "The Stormlight Archive", "Mistborn", "Jack Reacher"]  # fmt: skip

IDS = {name: uuid.uuid4() for name, _ in AUTHORS} | {name: uuid.uuid4() for name in SERIES}


def author_candidates() -> list[tuple[uuid.UUID, str, tuple[str, ...]]]:
    return [(IDS[n], n, (n, real) if real else (n,)) for n, real in AUTHORS]


def series_candidates() -> list[tuple[uuid.UUID, str, tuple[str, ...]]]:
    return [(IDS[n], n, (n,)) for n in SERIES]


def labels(found: list[tuple[uuid.UUID, str]]) -> list[str]:
    return [label for _, label in found]


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("J.D. Robb", "jdrobb"), ("J DM Robb", "jdmrobb"), ("  JD   ROBB ", "jdrobb"),
        ("The Dresden Files", "dresdenfiles"), ("the dresden files", "dresdenfiles"),
        ("Theodore", "theodore"), ("Ｊ．Ｄ． Robb", "jdrobb"), ("Le Guin, Ursula", "leguinursula"),
    ],
)  # fmt: skip
def test_loose_name_key(raw: str, key: str) -> None:
    assert loose_name_key(raw) == key


@pytest.mark.ac("005/AC-02")
def test_reported_typo_offers_the_intended_author_first() -> None:
    assert labels(similar_names("J DM Robb", author_candidates()))[0] == "J.D. Robb"


# SC-002: typical typos, each with the name the member meant.
TYPOS = {
    "JD Robb": "J.D. Robb", "Jim Bucher": "Jim Butcher", "Terry Pratchet": "Terry Pratchett",
    "Niel Gaiman": "Neil Gaiman", "Ursula Le Guin": "Ursula K. Le Guin",
    "Brandon Sandersen": "Brandon Sanderson", "JRR Tolkien": "J.R.R. Tolkien",
    "Agatha Cristie": "Agatha Christie", "Steven King": "Stephen King", "Lee Childs": "Lee Child",
    "Robin Hob": "Robin Hobb",
}  # fmt: skip
SERIES_TYPOS = {
    "Dresdin Files": "The Dresden Files", "Dresden Files": "The Dresden Files",
    "Disc World": "Discworld", "Wheel of Time": "The Wheel of Time",
    "Stormlight Archives": "The Stormlight Archive", "Mistborne": "Mistborn",
    "In Deth": "In Death",
}  # fmt: skip


@pytest.mark.ac("005/AC-02")
@pytest.mark.ac("005/AC-04")
def test_typical_typos_offer_the_intended_name() -> None:
    for typed, meant in TYPOS.items():
        found = labels(similar_names(typed, author_candidates()))
        assert meant in found and len(found) <= 3, (typed, found)
    for typed, meant in SERIES_TYPOS.items():
        found = labels(similar_names(typed, series_candidates()))
        assert meant in found and len(found) <= 3, (typed, found)
    assert len(TYPOS) + len(SERIES_TYPOS) >= 10


def test_new_names_get_no_suggestions() -> None:
    for typed in ("Janet Evanovich", "Ann Leckie", "Robert Galbraith", "Kim Harrison"):
        assert similar_names(typed, author_candidates()) == [], typed


def test_real_name_matches_the_pen_name() -> None:
    found = labels(similar_names("Nora Robert", author_candidates()))
    assert found[:2] == ["Nora Roberts", "J.D. Robb"] or found[:2] == ["J.D. Robb", "Nora Roberts"]
    assert "J.D. Robb" in labels(similar_names("Nora Roberts", author_candidates()))


def test_ranking_ties_limit_and_cutoff() -> None:
    a, b, c, d = (uuid.uuid4() for _ in range(4))
    candidates = [(a, "Smith B", ("Smith B",)), (b, "Smith A", ("Smith A",)),
                  (c, "Smith C", ("Smith C",)), (d, "Smith D", ("Smith D",))]  # fmt: skip
    found = similar_names("Smith", candidates)
    assert labels(found) == ["Smith A", "Smith B", "Smith C"]  # same score: by name; max 3
    assert similar_names("Smith", candidates, cutoff=0.95) == []
    assert similar_names("", candidates) == []


def test_parse_confirm_and_use_fields() -> None:
    """T008: the choice fields (data-model.md)."""
    from starlette.datastructures import FormData

    from book_tracker.web.forms import parse_add_book

    robb = uuid.uuid4()
    form = parse_add_book(
        FormData([
            ("title", "Naked in Death"), ("author_name_0", "J DM Robb"),
            ("confirm_author_0", "  J  DM Robb "), ("author_name_1", "Nora"),
            ("use_author_1", "not-a-uuid"), ("author_name_2", "Eve"),
            ("use_author_2", str(robb)), ("series_name", "In Deth"),
            ("confirm_series", "In Deth"), ("use_series", str(robb)),
        ])
    )  # fmt: skip
    rows = {row.index: row for row in form.authors}
    assert rows[0].confirmed == "J DM Robb" and rows[0].use_id is None
    assert rows[1].use_id is None and rows[1].confirmed == ""
    assert rows[2].use_id == robb
    assert form.series_confirmed == "In Deth" and form.use_series_id == robb
