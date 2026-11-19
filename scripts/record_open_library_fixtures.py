"""Record the Open Library responses the adapter tests replay (spec 002, research R14).

Run by hand, never in CI, when Open Library's response format changes:

    uv run python scripts/record_open_library_fixtures.py

It sends only author names and Open Library keys, with the same User-Agent as the app
(research R2), and spaces requests 2 s apart. It writes JSON files to
``tests/external/fixtures/open_library/``: the recorded ones, trimmed to the fields the
adapter asks for, and hand-made ones for cases the live site can't produce on demand.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from book_tracker.sources.open_library import (
    AUTHOR_SEARCH_LIMIT,
    WORK_FIELDS,
    WORKS_PAGE_SIZE,
    user_agent,
)

BASE = "https://openlibrary.org"
OUT = Path(__file__).resolve().parents[1] / "tests" / "external" / "fixtures" / "open_library"


def _get(client: httpx.Client, path: str, params: dict[str, Any]) -> dict[str, Any]:
    response = client.get(path, params=params)
    response.raise_for_status()
    time.sleep(2)
    data: dict[str, Any] = response.json()
    return data


def _save(name: str, data: dict[str, Any]) -> None:
    (OUT / name).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {name}")


def _authors(client: httpx.Client, q: str, keep: int | None = None) -> dict[str, Any]:
    data = _get(client, "/search/authors.json", {"q": q, "limit": AUTHOR_SEARCH_LIMIT})
    fields = ("key", "name", "birth_date", "death_date", "top_work", "work_count")
    docs = [{k: d[k] for k in fields if k in d} for d in data["docs"]][:keep]
    return {"numFound": len(docs) if keep else data["numFound"], "docs": docs}


def _work(n: int, title: str, author: str, key: str, **extra: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "key": f"/works/OL{n}W",
        "title": title,
        "first_publish_year": 1990 + n % 30,
        "author_name": [author],
        "author_key": [key],
        "edition_count": 1 + n % 7,
    }
    doc.update(extra)
    return doc


def _synthetic() -> None:
    key, name = "OL9000001A", "Prolific Writer"
    _save("works_duplicates.json", {"numFound": 3, "start": 0, "docs": [
        _work(101, "The Hidden Door", name, key, edition_count=3, isbn=["9780000000002"]),
        _work(102, "Hidden Door", name, key, edition_count=12, isbn=["0000000000"]),
        _work(103, "Another Story", name, key),
    ]})  # fmt: skip
    for page in (1, 2):
        docs = [
            _work(n, f"Volume {n}", name, key)
            for n in range((page - 1) * WORKS_PAGE_SIZE + 1, page * WORKS_PAGE_SIZE + 1)
        ]
        start = (page - 1) * WORKS_PAGE_SIZE
        _save(f"works_large_page{page}.json", {"numFound": 2500, "start": start, "docs": docs})
    _save("works_malformed.json", {"numFound": 3, "start": 0, "docs": [
        {"key": "/works/OL201W", "author_name": [name], "author_key": [key]},
        {"key": "/works/OL202W", "title": "No Author Listed"},
        _work(203, "A Good One", name, key),
    ]})  # fmt: skip
    _save("works_unknown_author.json", {"numFound": 0, "start": 0, "docs": []})
    _save("works_repeated_author.json", {"numFound": 1, "start": 0, "docs": [
        _work(301, "Written Twice", name, key,
              author_name=[name, "Co Author", name], author_key=[key, "OL9000002A", key]),
    ]})  # fmt: skip
    _save("works_long_values.json", {"numFound": 1, "start": 0, "docs": [
        _work(401, " ".join(["Longtitle"] * 40), "N" * 250, key,
              author_name=["Name " * 50], author_key=[key]),
    ]})  # fmt: skip


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": user_agent()}
    with httpx.Client(base_url=BASE, headers=headers, timeout=20) as client:
        _save("authors_brandon_sanderson.json", _authors(client, "brandon sanderson"))
        _save("authors_single.json", _authors(client, "ursula k. le guin", keep=1))
        _save("authors_none.json", _authors(client, "zzqx qqzz nobody"))
        params = {"author_key": "OL1394865A", "fields": ",".join(WORK_FIELDS),
                  "limit": WORKS_PAGE_SIZE, "page": 1}  # fmt: skip
        works = _get(client, "/search.json", params)
        keep = ("numFound", "start", "docs")
        _save("works_OL1394865A.json", {k: works[k] for k in keep if k in works})
    _synthetic()


if __name__ == "__main__":
    main()
