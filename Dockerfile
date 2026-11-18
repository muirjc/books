# Single deployable image (Constitution Principle VIII; research R12)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN uv sync --frozen --no-dev --no-editable \
    && chmod 0755 /usr/local/bin/entrypoint.sh \
    && useradd --system --uid 10001 --home-dir /app app

USER app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
