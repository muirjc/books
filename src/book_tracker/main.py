"""Application factory: one deployable serving the JSON API and the pages (Principle VIII)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles

from book_tracker.api import admin as api_admin
from book_tracker.api import auth as api_auth
from book_tracker.api import authors as api_authors
from book_tracker.api import books as api_books
from book_tracker.api import me as api_me
from book_tracker.api import readings as api_readings
from book_tracker.api import series as api_series
from book_tracker.api.errors import (
    Conflict,
    FieldProblem,
    Problem,
    ValidationProblem,
    register_error_handlers,
)
from book_tracker.logging import RequestLogMiddleware, configure_logging
from book_tracker.persistence.db import Database
from book_tracker.settings import Settings, get_settings
from book_tracker.sources.base import BookSource, UnavailableSource
from book_tracker.sources.open_library import OpenLibrarySource, make_client
from book_tracker.web.cookies import refresh_session_cookie
from book_tracker.web.routes import admin as web_admin
from book_tracker.web.routes import auth as web_auth
from book_tracker.web.routes import catalog as web_catalog
from book_tracker.web.routes import health as web_health
from book_tracker.web.routes import readings as web_readings
from book_tracker.web.routes import suggest as web_suggest
from book_tracker.web.security import SecurityHeadersMiddleware

STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"
API_PREFIX = "/api/v1"


def utc_now() -> datetime:
    return datetime.now(UTC)


def _book_source(settings: Settings, given: BookSource | None) -> tuple[BookSource, Any]:
    """The source to use, and an HTTP client to close on shutdown (research R14, R18).

    Under test, no app may call Open Library: without a given source it gets one that fails
    every call (Principle V).
    """
    if given is not None:
        return given, None
    if settings.environment == "test":
        return UnavailableSource(), None
    client = make_client(settings.openlibrary_base_url)
    source = OpenLibrarySource(client, timeout_seconds=settings.source_timeout_seconds)
    return source, client


def create_app(settings: Settings, *, book_source: BookSource | None = None) -> FastAPI:
    source, http_client = _book_source(settings, book_source)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if http_client is not None:
                await http_client.aclose()

    app = FastAPI(
        title="Family Book Tracker API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = Database.from_url(settings.database_url)
    app.state.clock = utc_now
    app.state.book_source = source

    configure_logging()
    app.middleware("http")(refresh_session_cookie)
    app.add_middleware(RequestLogMiddleware)
    # Added last, so it runs first: the HTTPS redirect happens before anything else.
    app.add_middleware(SecurityHeadersMiddleware, production=settings.is_production)
    register_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)
    api.include_router(api_auth.router)
    api.include_router(api_me.router)
    api.include_router(api_readings.router)
    api.include_router(api_books.router)
    api.include_router(api_authors.router)
    api.include_router(api_series.router)
    api.include_router(api_admin.router)
    app.include_router(api)

    app.include_router(web_auth.router)
    app.include_router(web_readings.router)
    app.include_router(web_admin.router)
    app.include_router(web_catalog.router)
    app.include_router(web_suggest.router)
    app.include_router(web_health.router)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    # FastAPI's documented way to customise the schema is to replace app.openapi.
    app.openapi = _openapi_builder(app)  # type: ignore[method-assign]
    return app


def _openapi_builder(app: FastAPI) -> Callable[[], dict[str, Any]]:
    """OpenAPI shaped like the contract: server ``/api/v1``, problem+json errors (R16)."""

    def build() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        from fastapi.openapi.utils import get_openapi

        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        schema["servers"] = [{"url": API_PREFIX}]
        schema["paths"] = {
            path.removeprefix(API_PREFIX) or "/": item
            for path, item in schema.get("paths", {}).items()
            if path.startswith(API_PREFIX)
        }
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        for model in (Problem, Conflict, ValidationProblem, FieldProblem):
            definition = model.model_json_schema(ref_template="#/components/schemas/{model}")
            for name, nested in definition.pop("$defs", {}).items():
                components.setdefault(name, nested)
            components[model.__name__] = definition
        for item in schema["paths"].values():
            for operation in item.values():
                responses = operation.get("responses", {})
                if "422" in responses:
                    responses["422"] = {
                        "description": "Request failed validation",
                        "content": {
                            "application/problem+json": {
                                "schema": {"$ref": "#/components/schemas/ValidationProblem"}
                            }
                        },
                    }
        for name in ("HTTPValidationError", "ValidationError"):
            components.pop(name, None)
        schema["components"]["securitySchemes"] = {
            "sessionCookie": {"type": "apiKey", "in": "cookie", "name": "__Host-session"}
        }
        app.openapi_schema = schema
        return schema

    return build


def __getattr__(name: str) -> Any:
    """``book_tracker.main:app`` for uvicorn, built from the environment on first use.

    Lazy, so importing this module (tests, the OpenAPI export) needs no environment.
    """
    if name == "app":
        application = create_app(get_settings())
        globals()["app"] = application
        return application
    raise AttributeError(name)
