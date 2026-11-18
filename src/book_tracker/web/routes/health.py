"""Unauthenticated health check for the container (spec section 10.4).

Healthy means the app can reach its database. Not part of the API contract, so it is
left out of the OpenAPI document. In production it answers plain HTTP (the health check
bypasses Caddy; see ``web/security.py``), and successful checks are not request-logged.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from book_tracker.persistence.db import Database

HEALTH_PATH = "/healthz"
DB_TIMEOUT_SECONDS = 3.0

router = APIRouter()
logger = logging.getLogger("book_tracker.health")


@router.get(HEALTH_PATH, include_in_schema=False)
async def healthz(request: Request) -> JSONResponse:
    database: Database = request.app.state.db
    try:
        async with asyncio.timeout(DB_TIMEOUT_SECONDS):
            async with database.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
    except Exception as exc:  # any failure to reach the database means unhealthy
        logger.warning("health check failed", extra={"error": type(exc).__name__})
        status, body = 503, {"status": "unavailable"}
    else:
        status, body = 200, {"status": "ok"}
    return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store"})
