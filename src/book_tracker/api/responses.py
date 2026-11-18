"""Shared ``responses=`` maps so the generated OpenAPI matches the contract (research R16).

Each entry references the contract's component name with ``application/problem+json``
content; ``main.custom_openapi`` adds the referenced components.
"""

from __future__ import annotations

from typing import Any

Responses = dict[int | str, dict[str, Any]]

PROBLEM_MEDIA = "application/problem+json"


def _problem(
    description: str, schema: str = "Problem", headers: dict[str, Any] | None = None
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "description": description,
        "content": {PROBLEM_MEDIA: {"schema": {"$ref": f"#/components/schemas/{schema}"}}},
    }
    if headers:
        entry["headers"] = headers
    return entry


UNAUTHENTICATED: Responses = {401: _problem("No valid session")}
FORBIDDEN: Responses = {403: _problem("code=csrf_failed, password_change_required or not_admin")}
CSRF_FAILED: Responses = {403: _problem("code=csrf_failed")}
PASSWORD_CHANGE_REQUIRED: Responses = {403: _problem("code=password_change_required")}
NOT_FOUND: Responses = {
    404: _problem("Does not exist, or belongs to another member (indistinguishable)")
}
CONFLICT: Responses = {409: _problem("Conflict", "Conflict")}
CATALOG_CONFLICT: Responses = {409: _problem("Uniqueness conflict in the catalog", "Conflict")}
PLAIN_CONFLICT: Responses = {409: _problem("Conflict")}
VALIDATION: Responses = {422: _problem("Request failed validation", "ValidationProblem")}
BAD_REQUEST: Responses = {400: _problem("Current password is wrong")}
LOGIN_FAILED: Responses = {401: _problem("Wrong login or password, or account deactivated")}
TOO_MANY_ATTEMPTS: Responses = {
    429: _problem(
        "Too many failed attempts for this login; retry after the lock ends",
        headers={
            "Retry-After": {
                "schema": {"type": "integer"},
                "description": "Seconds until sign-in is allowed",
            }
        },
    )
}


def merge(*maps: Responses) -> Responses:
    result: Responses = {}
    for item in maps:
        result.update(item)
    return result


# Common combinations
READ = merge(UNAUTHENTICATED, PASSWORD_CHANGE_REQUIRED)
READ_ONE = merge(UNAUTHENTICATED, PASSWORD_CHANGE_REQUIRED, NOT_FOUND)
WRITE = merge(UNAUTHENTICATED, FORBIDDEN, VALIDATION)
