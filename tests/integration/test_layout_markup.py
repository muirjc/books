"""Spec 003: the server-rendered parts of the responsive layout (contracts/ui-layout.md).

The browser checks are in tests/a11y/test_layout_003.py; these check the HTML they rely on:
the cells of a My books row, the filter fold state, and how book forms are grouped.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from html.parser import HTMLParser

import httpx
import pytest

from tests.conftest import Factory, TestUser, signed_in


@pytest.fixture
async def alice(factory: Factory) -> TestUser:
    return await factory.user("alice", display_name="Alice")


@pytest.fixture
async def member(
    alice: TestUser, client_factory: Callable[[], httpx.AsyncClient]
) -> httpx.AsyncClient:
    return await signed_in(client_factory(), alice)


class _Outline(HTMLParser):
    """Records (depth, tag, attrs) for every start tag, and text by the enclosing element."""

    VOID = {"input", "br", "img", "meta", "link", "hr"}

    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.tags: list[tuple[int, str, dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((self.depth, tag, {k: v or "" for k, v in attrs}))
        if tag not in self.VOID:
            self.depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag not in self.VOID:
            self.depth -= 1


def _rows(html: str) -> list[str]:
    body = html.split('<ul class="book-list reading-list"', 1)[1].split("</ul>", 1)[0]
    return re.findall(r"<li>(.*?)</li>", body, re.S)


def _cells(row: str) -> list[tuple[str, str]]:
    found = re.findall(r'<(?:a|div|span) class="(book-[a-z]+)[^"]*"[^>]*>(.*?)</(?:a|div|span)>',
                       row, re.S)  # fmt: skip
    return [(cls, re.sub(r"<[^>]+>|\s+", " ", text).strip()) for cls, text in found]


@pytest.mark.ac("003/AC-01")
@pytest.mark.ac("003/AC-03")
@pytest.mark.ac("003/AC-04")
async def test_list_rows_have_five_cells(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    author = await factory.author("Terry Pratchett", alice)
    mort = await factory.book("Mort", alice, author_ids=[author])
    sourcery = await factory.book("Sourcery", alice, author_ids=[author])
    await factory.entry(alice, mort, finished_on=date(2026, 3, 12), times_read=3)
    await factory.entry(alice, sourcery, status="reading")
    rows = _rows((await member.get("/")).text)
    assert len(rows) == 2
    first = dict(_cells(rows[0]))
    assert [c for c, _ in _cells(rows[0])] == [
        "book-title", "book-meta", "book-status", "book-finished", "book-times"
    ]  # fmt: skip
    assert first["book-title"] == "Mort"
    assert first["book-meta"] == "Terry Pratchett"
    assert first["book-status"] == "Finished"
    assert first["book-finished"] == "Finished 12 Mar 2026"
    assert first["book-times"] == "Read 3 times"
    second = dict(_cells(rows[1]))
    assert second["book-status"] == "Reading"
    assert second["book-finished"] == "" and second["book-times"] == ""


def _filters(html: str) -> tuple[str, list[tuple[int, str, dict[str, str]]]]:
    form = re.search(r"<form[^>]*role=\"search\"[^>]*>", html)
    assert form, "filter form"
    fold = re.search(r'data-fold="([a-z]+)"', form.group(0))
    outline = _Outline()
    outline.feed(html.split(form.group(0), 1)[1].split("</form>", 1)[0])
    return (fold.group(1) if fold else ""), outline.tags


@pytest.mark.ac("003/AC-05")
@pytest.mark.ac("003/AC-06")
@pytest.mark.parametrize(
    ("query", "fold"),
    [
        ("", "closed"),
        ("?status=reading", "open"),
        ("?q=x", "open"),
        ("?sort=author", "open"),
        ("?sort=title", "closed"),
    ],  # fmt: skip
)
async def test_filter_fold_state(member: httpx.AsyncClient, query: str, fold: str) -> None:
    html = (await member.get("/" + query)).text
    state, tags = _filters(html)
    assert state == fold
    toggle = [a for _, t, a in tags if t == "button" and "filters-toggle" in a.get("class", "")]
    assert len(toggle) == 1
    assert toggle[0]["aria-controls"] == "filter-extra"
    assert toggle[0]["aria-expanded"] == ("true" if fold == "open" else "false")
    assert "hidden" in toggle[0]
    extra_depth = next(d for d, _, a in tags if a.get("id") == "filter-extra")
    inside, outside = set(), set()
    started = False
    for depth, tag, attrs in tags:
        if attrs.get("id") == "filter-extra":
            started = True
            continue
        name = attrs.get("id") or (attrs.get("type") if tag == "button" else "")
        if started and depth > extra_depth:
            inside.add(name)
        else:
            started = started and depth > extra_depth
            outside.add(name)
    assert "q" in outside
    assert {"sort", "status", "author_id", "series_id", "submit"} <= inside


@pytest.mark.ac("003/AC-11")
@pytest.mark.ac("003/AC-12")
@pytest.mark.ac("003/AC-13")
@pytest.mark.ac("003/AC-15")
async def test_form_groups_and_pairs(
    member: httpx.AsyncClient, factory: Factory, alice: TestUser
) -> None:
    author = await factory.author("Terry Pratchett", alice)
    book = await factory.book("Mort", alice, author_ids=[author])
    entry = await factory.entry(alice, book)
    for path in ("/books/add", f"/entries/{entry}"):
        html = (await member.get(path)).text
        outline = _Outline()
        outline.feed(html)
        tags = outline.tags
        start = next(i for i, (_, _, a) in enumerate(tags) if a.get("class") == "form-columns")
        depth = tags[start][0]
        groups, group_inputs, after = [], [], []
        closed = False
        for d, tag, attrs in tags[start + 1 :]:
            if d < depth:
                break  # left the form
            if closed or d <= depth:
                closed = True
                after.append((tag, attrs))
                continue
            if d == depth + 1:
                groups.append(tag)
                group_inputs.append([])
            if tag in ("input", "select", "textarea") and attrs.get("type") != "hidden":
                group_inputs[-1].append(attrs.get("id", ""))
        assert len(groups) == 2, (path, groups)
        assert group_inputs[0][0] == "title", path
        assert {"author_name_0", "series_name", "series_number", "isbn_13"} <= set(
            group_inputs[0]
        ), path
        assert group_inputs[1][:2] == ["status", "finished_on"], path
        assert "notes" in group_inputs[1], path
        assert any(t == "button" and a.get("type") == "submit" for t, a in after), path
        pairs = []
        for i, (d, _, attrs) in enumerate(tags):
            if attrs.get("class") != "field-row":
                continue
            ids = []
            for d2, tag, a2 in tags[i + 1 :]:
                if d2 <= d:
                    break
                if tag in ("input", "select") and a2.get("type") != "hidden":
                    ids.append(a2.get("id"))
            pairs.append(tuple(ids))
        assert ("series_name", "series_number") in pairs, (path, pairs)
        assert ("status", "finished_on") in pairs, (path, pairs)
