#!/bin/sh
# Restore the Family Book Tracker from its backups (spec section 10.6).
#
#   books-restore.sh check    [--snapshot ID] [--dump FILE]
#       Restore into a scratch database (books_restore_check), print row counts next to
#       the live database's, then drop it. The live data isn't touched. This is the
#       restore test.
#   books-restore.sh database --yes [--snapshot ID] [--dump FILE]
#       Replace the live database. Stops the app first; starts it again if it was running.
#   books-restore.sh caddy-ca --yes [--snapshot ID]
#       Put Caddy's internal CA back, so devices that trust the old root keep working.
#
# Source: the restic snapshot ID (default: latest), or with --dump a plain dump file from
# the NAS (no restic or restic password needed). Settings as for books-backup.sh.
set -eu
umask 077

fail() {
    echo "books-restore: $*" >&2
    exit 1
}
usage() {
    fail "usage: books-restore.sh check|database|caddy-ca [--yes] [--snapshot ID] [--dump FILE]"
}

[ $# -ge 1 ] || usage
action="$1"
shift
yes=no
snapshot=latest
dump_file=
while [ $# -gt 0 ]; do
    case "$1" in
    --yes) yes=yes ;;
    --snapshot) snapshot="${2:?}"; shift ;;
    --dump) dump_file="${2:?}"; shift ;;
    *) usage ;;
    esac
    shift
done
case "$action" in
check) ;;
database | caddy-ca)
    [ "$yes" = yes ] || fail "$action replaces live data; run again with --yes to confirm"
    ;;
*) usage ;;
esac

: "${COMPOSE_DIR:?set COMPOSE_DIR}"
STAGING_DIR="${STAGING_DIR:-/var/lib/books-backup}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-$COMPOSE_DIR/.env}"

compose() {
    docker compose --project-directory "$COMPOSE_DIR" --env-file "$COMPOSE_ENV_FILE" "$@"
}
psql_db() {
    compose exec -T db psql -U books -d "$1" -v ON_ERROR_STOP=1 -At -c "$2"
}

work="$STAGING_DIR/restore"
rm -rf "$work"
mkdir -p "$work"
trap 'rm -rf "$work"' EXIT

# Fetch the backed-up files (books.dump, caddy-pki/) from restic into $work/files.
from_restic() {
    : "${RESTIC_REPOSITORY:?set RESTIC_REPOSITORY}"
    : "${RESTIC_PASSWORD_FILE:?set RESTIC_PASSWORD_FILE}"
    export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE
    # Snapshots hold one path, the staging directory of the run that made them.
    path=$(restic snapshots --json --host books --tag nightly "$snapshot" |
        sed -n 's/.*"paths":\["\([^"]*\)".*/\1/p' | head -n 1)
    [ -n "$path" ] || fail "no restic snapshot '$snapshot'"
    echo "books-restore: restoring snapshot $snapshot ($path)"
    restic restore --quiet "$snapshot:$path" --target "$work/files"
}

dump_path() {
    if [ -n "$dump_file" ]; then
        [ -f "$dump_file" ] || fail "no dump file $dump_file"
        echo "$dump_file"
    else
        from_restic >&2
        echo "$work/files/books.dump"
    fi
}

TABLES="app_user book author series book_author book_summary reading_entry"
counts() {
    query=""
    for table in $TABLES; do
        query="$query${query:+ UNION ALL }SELECT '$table', count(*) FROM $table"
    done
    psql_db "$1" "$query" | tr '|' ' '
}

pg_restore_into() {
    compose exec -T db pg_restore -U books -d "$1" --no-owner --exit-on-error <"$2"
}

case "$action" in
check)
    dump=$(dump_path)
    scratch=books_restore_check
    compose exec -T db dropdb -U books --if-exists "$scratch"
    compose exec -T db createdb -U books "$scratch"
    trap 'compose exec -T db dropdb -U books --if-exists "$scratch" >/dev/null 2>&1; rm -rf "$work"' EXIT
    pg_restore_into "$scratch" "$dump"
    version=$(psql_db "$scratch" "SELECT version_num FROM alembic_version")
    echo "Restored (schema version $version):"
    counts "$scratch"
    echo "Live database now:"
    counts books
    echo "Restore check passed."
    ;;
database)
    dump=$(dump_path)
    running=$(compose ps --status running --services | grep -qx app && echo yes || echo no)
    echo "books-restore: stopping the app and replacing the database"
    compose stop app >/dev/null 2>&1 || true
    compose exec -T db dropdb -U books --if-exists --force books
    compose exec -T db createdb -U books -O books books
    pg_restore_into books "$dump"
    [ "$running" = yes ] && compose start app
    echo "Database restored:"
    counts books
    ;;
caddy-ca)
    [ -z "$dump_file" ] || fail "caddy-ca restores from restic only"
    from_restic
    [ -f "$work/files/caddy-pki/authorities/local/root.key" ] ||
        fail "snapshot $snapshot has no Caddy CA"
    echo "books-restore: putting Caddy's CA back"
    # Drop the current CA and the certificates it issued, so Caddy reissues from the
    # restored CA.
    compose exec -T proxy rm -rf /data/caddy/pki /data/caddy/certificates/local
    compose cp "$work/files/caddy-pki" proxy:/data/caddy/pki
    compose restart proxy
    echo "Caddy's CA restored."
    ;;
esac
