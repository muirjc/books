#!/bin/sh
# Container start-up (research R12): migrate, optionally create the first Admin, serve.
set -eu

alembic upgrade head

if [ -n "${BOOK_TRACKER_ADMIN_LOGIN:-}" ]; then
    book-tracker create-admin \
        --login "$BOOK_TRACKER_ADMIN_LOGIN" \
        --display-name "${BOOK_TRACKER_ADMIN_DISPLAY_NAME:-$BOOK_TRACKER_ADMIN_LOGIN}" \
        --if-missing
fi

exec uvicorn book_tracker.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
