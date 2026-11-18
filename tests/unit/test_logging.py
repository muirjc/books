"""T023: logs never contain secrets or personal notes (research R19, Principle IX)."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from book_tracker.logging import REDACTED, JsonFormatter, RedactingFilter, redact
from book_tracker.main import create_app
from book_tracker.settings import Settings
from tests.conftest import make_client


def test_redact_nested_values() -> None:
    data = {
        "login": "alice",
        "password": "secret",
        "nested": {"token": "abc", "notes": "private thoughts", "keep": 1},
        "items": [{"csrf_token": "x"}, {"title": "ok"}],
        "headers": {"Cookie": "__Host-session=abc", "set-cookie": "a=b", "accept": "*/*"},
    }
    assert redact(data) == {
        "login": "alice",
        "password": REDACTED,
        "nested": {"token": REDACTED, "notes": REDACTED, "keep": 1},
        "items": [{"csrf_token": REDACTED}, {"title": "ok"}],
        "headers": {"Cookie": REDACTED, "set-cookie": REDACTED, "accept": "*/*"},
    }


def test_filter_redacts_record_args_and_extras() -> None:
    record = logging.LogRecord(
        "t", logging.INFO, __file__, 1, "event %s", ({"password": "p"},), None
    )
    record.notes = "private"
    record.detail = {"token": "t", "status": 200}
    assert RedactingFilter().filter(record)
    # LogRecord unwraps a single mapping argument into the mapping itself.
    assert record.args == {"password": REDACTED}
    assert record.notes == REDACTED
    assert record.detail == {"token": REDACTED, "status": 200}


def test_json_formatter_outputs_redacted_extras() -> None:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello", None, None)
    record.route = "/x/{id}"
    record.password = "should not appear"
    RedactingFilter().filter(record)
    line = json.loads(JsonFormatter().format(record))
    assert line["message"] == "hello"
    assert line["route"] == "/x/{id}"
    assert line["password"] == REDACTED


@pytest.fixture(scope="module")
def logged_app(settings: Settings) -> Any:
    probe = create_app(settings)

    @probe.get("/api/v1/_probe/items/{item_id}")
    async def item(item_id: str) -> dict[str, str]:
        return {"id": item_id}

    return probe


async def test_request_log_uses_route_template(
    logged_app: Any, app: Any, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="book_tracker.request")
    async with make_client(logged_app) as client:
        response = await client.get("/api/v1/_probe/items/secret-entry-id?notes=private")
    assert response.status_code == 200
    records = [r for r in caplog.records if r.name == "book_tracker.request"]
    assert len(records) == 1
    record: Any = records[0]
    assert record.method == "GET"
    assert record.route == "/api/v1/_probe/items/{item_id}"
    assert record.status == 200
    assert record.duration_ms >= 0
    rendered = json.dumps(record.__dict__, default=str)
    assert "secret-entry-id" not in rendered
    assert "private" not in rendered


async def test_unmatched_route_logged_without_path(
    logged_app: Any, app: Any, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="book_tracker.request")
    async with make_client(logged_app) as client:
        await client.get("/no/such/page/abc123")
    record: Any = [r for r in caplog.records if r.name == "book_tracker.request"][-1]
    assert record.route == "<unmatched>"
    assert record.status == 404
    assert "abc123" not in json.dumps(record.__dict__, default=str)


async def test_nested_routes_are_logged_by_template(
    client: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """Routes from included routers (API and pages) log their full template, not the path."""
    caplog.set_level(logging.INFO, logger="book_tracker.request")
    entry = "11111111-2222-4333-8444-555555555555"
    await client.get(f"/api/v1/me/readings/{entry}")
    await client.get(f"/entries/{entry}")
    await client.get("/sign-in")
    routes = [r.route for r in caplog.records if r.name == "book_tracker.request"]  # type: ignore[attr-defined]  # set via extra=
    assert routes == ["/api/v1/me/readings/{entry_id}", "/entries/{entry_id}", "/sign-in"]
