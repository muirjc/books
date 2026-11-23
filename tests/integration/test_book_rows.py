"""Spec 015 User Story 2: one row layout with my own status, on the catalog-style lists."""

from __future__ import annotations

import re
import uuid
from typing import Any

import httpx
import pytest

from tests.conftest import Factory, TestUser
from tests.integration.test_flow_fixes import text_of
from tests.integration.test_quick_add import alice_fixture, member_fixture, world_fixture  # noqa: F401


def row(page: str, book: uuid.UUID) -> str:
    found = re.search(rf'<li[^>]*id="book-{book}"[^>]*>.*?</li>', page, re.S)
    assert found, book
    return found.group(0)


@pytest.mark.ac("015/AC-07")
@pytest.mark.ac("015/AC-08")
@pytest.mark.ac("015/AC-10")
async def test_one_row_layout_with_my_status(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    await factory.execute("UPDATE reading_entry SET status = 'reading' WHERE id = :e",
                          e=w["mort_entry"])  # fmt: skip
    for path in ("/catalog", f"/authors/{w['terry']}"):
        page = (await member.get(path)).text
        mort = row(page, w["mort"])
        title, meta, status = (mort.find('class="book-title"'), mort.find('class="book-meta"'),
                               mort.find('class="row-status"'))  # fmt: skip
        assert -1 < title < meta < status, path
        assert f'href="/entries/{w["mort_entry"]}"' in mort  # the title opens my entry
        assert re.search(
            rf'<a class="badge status-link" href="/entries/{w["mort_entry"]}">Reading'
            r'<span class="visually-hidden">: “Mort”</span></a>', mort,
        ), path  # fmt: skip
        assert "Discworld #4" in text_of(mort), path  # the series on author rows too
        assert "On my list" not in text_of(mort)
        gods = row(page, w["gods"])
        assert "Not on my list" in text_of(gods)
        assert f'href="/catalog/books/{w["gods"]}/edit"' in gods  # not mine: Edit book
        assert gods.find('class="row-status"') < gods.find("want-to-read")


@pytest.mark.ac("015/AC-07")
async def test_upcoming_rows_share_the_layout(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    page = (await member.get("/upcoming")).text
    soon = row(page, w["soon"])
    assert "Coming" in text_of(soon) and "Not on my list" in text_of(soon)
    entry = await factory.entry(alice, w["soon"], status="want_to_read")
    page = (await member.get("/upcoming")).text
    soon = row(page, w["soon"])
    assert f'<a class="badge status-link" href="/entries/{entry}">Want to read' in soon


@pytest.mark.ac("015/AC-09")
async def test_series_status_badges(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser, w: dict[str, Any]
) -> None:
    await factory.execute(
        "UPDATE reading_entry SET status = 'finished', finished_on = '2025-03-03' WHERE id = :e",
        e=w["mort_entry"],
    )
    await factory.entry(alice, w["tales"], status="reading")
    page = (await member.get(f"/series/{w['disc']}")).text
    mort = re.search(r"<li[^>]*>(?:(?!</li>).)*Mort(?:(?!</li>).)*</li>", page, re.S)
    assert mort and re.search(r'class="badge status-link"[^>]*>Finished', mort.group(0))
    assert "3 Mar 2025" in text_of(mort.group(0))
    story = re.search(r'<li class="series-story">.*?</li>', page, re.S)
    assert story and re.search(r'class="badge status-link"[^>]*>Reading', story.group(0))


@pytest.mark.ac("015/AC-11")
async def test_only_my_status(
    member: httpx.AsyncClient, factory: Factory, w: dict[str, Any]
) -> None:
    bob = await factory.user("bob")
    await factory.entry(bob, w["gods"], status="reading")
    for path in ("/catalog", f"/authors/{w['terry']}", f"/series/{w['disc']}"):
        page = (await member.get(path)).text
        gods = row(page, w["gods"]) if path != f"/series/{w['disc']}" else page
        assert "Reading" not in text_of(gods) or path == f"/series/{w['disc']}", path
    series = (await member.get(f"/series/{w['disc']}")).text
    small = re.search(r"<li[^>]*>(?:(?!</li>).)*Small Gods(?:(?!</li>).)*</li>", series, re.S)
    assert small and "Not on my list" in text_of(small.group(0))
