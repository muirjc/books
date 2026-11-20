"""Validate httpx responses against the committed OpenAPI contract (task T012)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from openapi_core import Config, OpenAPI
from openapi_core.datatypes import RequestParameters
from werkzeug.datastructures import Headers, ImmutableMultiDict

SPECS = Path(__file__).resolve().parents[2] / "specs"
DEFAULT_FEATURE = "001-family-reading-list"


def contract_path(feature: str) -> Path:
    """The committed contract of one feature, e.g. ``002-author-book-import``."""
    return SPECS / feature / "contracts" / "openapi.yaml"


class HttpxOpenAPIRequest:
    def __init__(self, request: httpx.Request) -> None:
        self._request = request
        url = urlparse(str(request.url))
        self._url = url
        cookies: dict[str, str] = {}
        for part in request.headers.get("cookie", "").split(";"):
            if "=" in part:
                key, _, value = part.strip().partition("=")
                cookies[key] = value
        self.parameters = RequestParameters(
            query=ImmutableMultiDict(parse_qs(url.query)),
            header=Headers(dict(request.headers)),
            cookie=ImmutableMultiDict(cookies),
        )

    @property
    def host_url(self) -> str:
        return f"{self._url.scheme}://{self._url.netloc}"

    @property
    def path(self) -> str:
        return self._url.path

    @property
    def method(self) -> str:
        return self._request.method.lower()

    @property
    def body(self) -> bytes | None:
        return self._request.content or None

    @property
    def content_type(self) -> str:
        return self._request.headers.get("content-type", "").lower()


class HttpxOpenAPIResponse:
    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def content_type(self) -> str:
        return self._response.headers.get("content-type", "").lower()

    @property
    def headers(self) -> Headers:
        return Headers(dict(self._response.headers))

    @property
    def data(self) -> bytes | None:
        return self._response.content or None


_contracts: dict[str, OpenAPI] = {}


def contract(feature: str = DEFAULT_FEATURE) -> OpenAPI:
    if feature not in _contracts:
        # openapi-core has no built-in parser for problem+json; it is plain JSON.
        config = Config(extra_media_type_deserializers={"application/problem+json": json.loads})
        _contracts[feature] = OpenAPI.from_file_path(str(contract_path(feature)), config=config)
    return _contracts[feature]


def assert_matches_contract(response: httpx.Response, feature: str = DEFAULT_FEATURE) -> None:
    """Fail unless the response is one the feature's contract defines for its operation."""
    contract(feature).validate_response(
        HttpxOpenAPIRequest(response.request), HttpxOpenAPIResponse(response)
    )


@pytest.fixture
def matches_contract() -> Callable[[httpx.Response], None]:
    return assert_matches_contract


@pytest.fixture
def matches_contract_002() -> Callable[[httpx.Response], None]:
    """Spec 002's contract: the author-import operations."""
    return lambda response: assert_matches_contract(response, "002-author-book-import")
