"""Problem responses for the JSON API; redirects and HTML error pages for pages.

Paths under ``/api/`` get ``application/problem+json`` bodies matching the contract's
``Problem``, ``Conflict`` and ``ValidationProblem`` schemas. Other paths get a redirect
(sign-in, forced password change) or a rendered HTML error page.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, WithJsonSchema
from starlette.exceptions import HTTPException as StarletteHTTPException

from book_tracker.services.errors import (
    ConflictError,
    ForbiddenError,
    InvalidCredentials,
    NotAuthenticated,
    NotFoundError,
    PasswordChangeRequired,
    ServiceError,
    SourceUnavailable,
    TooManyAttempts,
    ValidationFailed,
    WrongCurrentPassword,
)

PROBLEM_JSON = "application/problem+json"


# Optional text fields are omitted when empty (``exclude_none``), never sent as null, so the
# schema documents them as plain strings.
OmittedWhenEmpty = Annotated[str | None, WithJsonSchema({"type": "string"})]


class Problem(BaseModel):
    code: str
    title: str
    detail: OmittedWhenEmpty = None


class Conflict(Problem):
    existing_id: uuid.UUID
    existing_label: OmittedWhenEmpty = None


class FieldProblem(BaseModel):
    field: str
    message: str


class ValidationProblem(Problem):
    errors: list[FieldProblem]


def is_api(request: Request) -> bool:
    return request.url.path.startswith("/api/")


def problem(status: int, body: BaseModel, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        body.model_dump(mode="json", exclude_none=True),
        status_code=status,
        media_type=PROBLEM_JSON,
        headers=headers,
    )


def _field_name(loc: tuple[Any, ...]) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "header", "cookie")]
    return ".".join(parts) or "request"


def _clean_message(message: str) -> str:
    return message.removeprefix("Value error, ")


def validation_problem(errors: list[FieldProblem]) -> ValidationProblem:
    return ValidationProblem(
        code="validation_failed", title="Some fields need attention", errors=errors
    )


def _html_error(request: Request, status: int, title: str) -> Response:
    from book_tracker.web.rendering import render_error

    return render_error(request, status, title)


def _status_for(exc: ServiceError) -> int:
    if isinstance(exc, NotAuthenticated | InvalidCredentials):
        return 401
    if isinstance(exc, ForbiddenError | PasswordChangeRequired):
        return 403
    if isinstance(exc, NotFoundError):
        return 404
    if isinstance(exc, ConflictError):
        return 409
    if isinstance(exc, ValidationFailed):
        return 422
    if isinstance(exc, TooManyAttempts):
        return 429
    if isinstance(exc, SourceUnavailable):
        return 503
    if isinstance(exc, WrongCurrentPassword):
        return 400
    return 400


async def service_error_handler(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, ServiceError):  # pragma: no cover - registered for ServiceError
        raise exc
    status = _status_for(exc)
    if not is_api(request):
        if isinstance(exc, NotAuthenticated):
            return ui_redirect(request, "/sign-in")
        if isinstance(exc, PasswordChangeRequired):
            return ui_redirect(request, "/account/password")
        return _html_error(request, status, exc.title)
    headers = None
    body: BaseModel
    if isinstance(exc, ConflictError) and exc.existing_id is not None:
        body = Conflict(
            code=exc.code,
            title=exc.title,
            existing_id=exc.existing_id,
            existing_label=exc.existing_label,
        )
    elif isinstance(exc, ValidationFailed):
        body = validation_problem(
            [FieldProblem(field=e.field, message=e.message) for e in exc.errors]
        )
    else:
        body = Problem(code=exc.code, title=exc.title)
    if isinstance(exc, TooManyAttempts):
        headers = {"Retry-After": str(exc.retry_after)}
    return problem(status, body, headers)


async def request_validation_handler(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, RequestValidationError):  # pragma: no cover
        raise exc
    errors = [
        FieldProblem(field=_field_name(tuple(e["loc"])), message=_clean_message(e["msg"]))
        for e in exc.errors()
    ]
    if not is_api(request):
        return _html_error(request, 422, "Some fields need attention")
    return problem(422, validation_problem(errors))


async def http_exception_handler(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, StarletteHTTPException):  # pragma: no cover
        raise exc
    if not is_api(request):
        title = "Not found" if exc.status_code == 404 else str(exc.detail)
        return _html_error(request, exc.status_code, title)
    code = "not_found" if exc.status_code == 404 else f"http_{exc.status_code}"
    title = "Not found" if exc.status_code == 404 else str(exc.detail)
    return problem(
        exc.status_code, Problem(code=code, title=title), headers=getattr(exc, "headers", None)
    )


def ui_redirect(request: Request, location: str) -> Response:
    """303 for normal requests; ``HX-Redirect`` for HTMX so the whole page navigates."""
    if request.headers.get("hx-request") == "true":
        return Response(status_code=200, headers={"HX-Redirect": location})
    return RedirectResponse(location, status_code=303)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ServiceError, service_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
