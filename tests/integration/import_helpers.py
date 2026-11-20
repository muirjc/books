"""Shared set-up for spec 002's API and page tests."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from tests.conftest import Factory, TestUser, signed_in, ui_csrf
from tests.fakes import FakeBookSource, author, listing, work

KEY = "OL1A"
WORKS_URL = f"/api/v1/import/authors/{KEY}/works"


def stock(ol: FakeBookSource, count: int = 3) -> None:
    """Ann Author with ``count`` works, findable by "ann author"."""
    ol.authors["ann author"] = [author(KEY, "Ann Author", count)]
    ol.works[KEY] = listing(KEY, [work(n, f"Book {n}") for n in range(1, count + 1)])


async def member(
    factory: Factory, make: Callable[[], httpx.AsyncClient], login: str
) -> tuple[TestUser, httpx.AsyncClient]:
    user = await factory.user(login)
    return user, await signed_in(make(), user)


async def import_via_api(
    client: httpx.AsyncClient, keys: list[str], **body: object
) -> httpx.Response:
    listed = await client.get(WORKS_URL)
    assert listed.status_code == 200, listed.text
    return await client.post(
        "/api/v1/me/imports", json={"author_key": KEY, "work_keys": keys, **body}
    )


async def confirm_via_page(
    client: httpx.AsyncClient, keys: list[str], status: str = "finished"
) -> httpx.Response:
    page = await client.get(f"/import/authors/{KEY}")
    assert page.status_code == 200, page.text
    token = await ui_csrf(client)
    data = [("csrf_token", token), ("status", status), *[("work", k) for k in keys]]
    return await client.post(
        f"/import/authors/{KEY}",
        content=httpx.QueryParams(data).__str__(),
        headers={"Content-Type": "application/x-www-form-urlencoded", "X-CSRF-Token": ""},
    )
