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

# --no-access-log: uvicorn's access log records raw paths and query strings; the app's own
# request log records route templates only (research R19).
exec uvicorn book_tracker.main:app --host 0.0.0.0 --port 8000 --workers 2 \
    --proxy-headers --forwarded-allow-ips='*' --no-access-log
