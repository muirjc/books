#!/bin/sh
# Nightly backup of the Family Book Tracker (spec section 10.6). Run by books-backup.timer.
#
# 1. pg_dump (custom format) from the db container; checked with pg_restore --list.
# 2. Caddy's internal CA (keys and certificates) from the proxy container.
# 3. A plain copy of the dump on the NAS: dumps/books-<UTC time>.dump, KEEP_DAYS kept.
# 4. Dump and CA into the encrypted restic repository (on the NAS), KEEP_DAYS daily
#    snapshots kept; then restic check.
# 5. NAS_DIR/last-success gets the time of the run.
#
# The CA's private keys are written in plain form only to STAGING_DIR on the Pi (mode
# 700), never to the NAS, and are deleted once restic has them.
#
# Settings come from the environment (see backup.env.example): COMPOSE_DIR, NAS_DIR,
# RESTIC_REPOSITORY, RESTIC_PASSWORD_FILE, STAGING_DIR, KEEP_DAYS, and optionally
# COMPOSE_ENV_FILE and COMPOSE_PROJECT_NAME.
set -eu
umask 077

fail() {
    echo "books-backup: $*" >&2
    exit 1
}

: "${COMPOSE_DIR:?set COMPOSE_DIR}"
: "${NAS_DIR:?set NAS_DIR}"
: "${RESTIC_REPOSITORY:?set RESTIC_REPOSITORY}"
: "${RESTIC_PASSWORD_FILE:?set RESTIC_PASSWORD_FILE}"
STAGING_DIR="${STAGING_DIR:-/var/lib/books-backup}"
KEEP_DAYS="${KEEP_DAYS:-30}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-$COMPOSE_DIR/.env}"
export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE

compose() {
    docker compose --project-directory "$COMPOSE_DIR" --env-file "$COMPOSE_ENV_FILE" "$@"
}

# The marker file lives on the NAS share itself, so it is missing whenever the share
# isn't mounted, and the backup never fills the Pi's own disk by mistake.
[ -f "$NAS_DIR/.books-backup-target" ] ||
    fail "NAS not mounted: $NAS_DIR/.books-backup-target is missing"
[ -r "$RESTIC_PASSWORD_FILE" ] || fail "can't read RESTIC_PASSWORD_FILE $RESTIC_PASSWORD_FILE"
restic cat config >/dev/null 2>&1 ||
    fail "no restic repository at $RESTIC_REPOSITORY (create it once with: restic init)"

stamp=$(date -u +%Y%m%dT%H%M%SZ)
work="$STAGING_DIR/current"
rm -rf "$work"
mkdir -p "$work"
trap 'rm -rf "$work"' EXIT

echo "books-backup: dumping the database"
compose exec -T db pg_dump -U books -d books --format=custom >"$work/books.dump"
compose exec -T db pg_restore --list <"$work/books.dump" >/dev/null ||
    fail "the new dump doesn't read back"

echo "books-backup: copying Caddy's CA"
compose cp proxy:/data/caddy/pki "$work/caddy-pki"
[ -f "$work/caddy-pki/authorities/local/root.key" ] || fail "Caddy's CA keys weren't found"

echo "books-backup: plain dump to the NAS"
mkdir -p "$NAS_DIR/dumps"
cp "$work/books.dump" "$NAS_DIR/dumps/books-$stamp.dump.partial"
mv "$NAS_DIR/dumps/books-$stamp.dump.partial" "$NAS_DIR/dumps/books-$stamp.dump"
find "$NAS_DIR/dumps" -name 'books-*.dump*' -type f -mtime +"$KEEP_DAYS" -delete

echo "books-backup: encrypted snapshot to restic"
restic backup --quiet --host books --tag nightly "$work"
restic forget --quiet --host books --tag nightly --keep-daily "$KEEP_DAYS" --prune
restic check --quiet

echo "$stamp" >"$NAS_DIR/last-success"
echo "books-backup: done ($stamp)"
