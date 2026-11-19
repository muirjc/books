"""Nightly backup and restore on the Pi (spec section 10.6; release gate T118, books-buh.9).

These run the real scripts against the real ``db`` and ``proxy`` services from
``deploy/pi/compose.yaml``, under a throwaway Compose project, with a temporary directory
standing in for the NAS. They need Docker and restic; run with ``pytest -m deploy``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy" / "pi"
BACKUP = DEPLOY / "backup" / "books-backup.sh"
RESTORE = DEPLOY / "backup" / "books-restore.sh"
MARKER = ".books-backup-target"

pytestmark = pytest.mark.deploy


def _missing_tools() -> list[str]:
    missing = [tool for tool in ("docker", "restic") if shutil.which(tool) is None]
    if not missing and subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        missing.append("a running Docker daemon")
    return missing


@pytest.fixture(scope="module", autouse=True)
def _tools() -> None:
    missing = _missing_tools()
    if missing:
        message = f"deploy tests need {', '.join(missing)}"
        if os.environ.get("BOOKS_REQUIRE_DEPLOY_TESTS"):
            pytest.fail(message)  # CI must not skip these silently
        pytest.skip(message)


@dataclass
class Stack:
    project: str
    env_file: Path
    nas: Path
    staging: Path
    password_file: Path

    @property
    def env(self) -> dict[str, str]:
        return {
            **os.environ,
            "COMPOSE_DIR": str(DEPLOY),
            "COMPOSE_ENV_FILE": str(self.env_file),
            "COMPOSE_PROJECT_NAME": self.project,
            "NAS_DIR": str(self.nas),
            "RESTIC_REPOSITORY": str(self.nas / "restic"),
            "RESTIC_PASSWORD_FILE": str(self.password_file),
            "STAGING_DIR": str(self.staging),
            "KEEP_DAYS": "30",
        }

    def compose(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["docker", "compose", "--project-directory", str(DEPLOY),
             "--env-file", str(self.env_file), "-p", self.project, *args],
            capture_output=True, text=True, check=check,
        )  # fmt: skip

    def sql(self, query: str, database: str = "books") -> str:
        result = self.compose("exec", "-T", "db", "psql", "-U", "books", "-d", database,
                              "-At", "-c", query)  # fmt: skip
        return result.stdout.strip()

    def run(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["sh", str(script), *args], env=self.env, capture_output=True, text=True
        )

    def restic(self, *args: str) -> str:
        return subprocess.run(
            ["restic", *args], env=self.env, capture_output=True, text=True, check=True
        ).stdout

    def root_fingerprint(self) -> str:
        pem = self.compose("exec", "-T", "proxy", "cat",
                           "/data/caddy/pki/authorities/local/root.crt").stdout  # fmt: skip
        return subprocess.run(
            ["openssl", "x509", "-noout", "-fingerprint", "-sha256"],
            input=pem, capture_output=True, text=True, check=True,
        ).stdout.strip()  # fmt: skip


def _wait_for_ca(stack: Stack) -> None:
    for _ in range(60):
        probe = ("test", "-f", "/data/caddy/pki/authorities/local/root.crt")
        if stack.compose("exec", "-T", "proxy", *probe, check=False).returncode == 0:
            return
        time.sleep(1)
    raise AssertionError("Caddy never created its internal CA")


@pytest.fixture(scope="module")
def stack(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Stack]:
    base = tmp_path_factory.mktemp("pi")
    env_file = base / ".env"
    env_file.write_text(
        "PI_LAN_IP=127.0.0.1\n"
        f"POSTGRES_PASSWORD={uuid.uuid4().hex}\n"
        f"BOOK_TRACKER_SECRET_KEY={uuid.uuid4().hex}{uuid.uuid4().hex}\n"
        "BOOK_TRACKER_ADMIN_LOGIN=admin\n"
        "BOOK_TRACKER_ADMIN_DISPLAY_NAME=Admin\n"
        f"BOOK_TRACKER_ADMIN_PASSWORD={uuid.uuid4().hex}\n"
        f"BOOKS_DATA_DIR={base / 'data'}\n"
    )
    nas = base / "nas"
    nas.mkdir()
    (nas / MARKER).touch()
    password_file = base / "restic-password"
    password_file.write_text(uuid.uuid4().hex)
    stack = Stack(f"books-bk-{uuid.uuid4().hex[:8]}", env_file, nas, base / "staging",
                  password_file)  # fmt: skip
    try:
        stack.compose("up", "-d", "--no-deps", "--wait", "db", "proxy")
        # The real schema and a first Admin, made by the published app image.
        stack.compose("run", "--rm", "--no-deps", "--entrypoint", "sh", "app", "-c",
                      "alembic upgrade head && book-tracker create-admin --login admin "
                      "--display-name Admin")  # fmt: skip
        _wait_for_ca(stack)
        stack.restic("init")
        yield stack
    finally:
        stack.compose("down", "-v", "--remove-orphans", check=False)
        # PostgreSQL's files belong to the container's postgres user.
        subprocess.run(["docker", "run", "--rm", "-v", f"{base}:/b", "alpine",
                        "rm", "-rf", "/b/data"], capture_output=True)  # fmt: skip


def _backup(stack: Stack) -> None:
    result = stack.run(BACKUP)
    assert result.returncode == 0, result.stderr


def test_backup_writes_dump_to_nas_and_encrypted_snapshot(stack: Stack) -> None:
    _backup(stack)
    dumps = sorted((stack.nas / "dumps").glob("books-*.dump"))
    assert len(dumps) == 1
    assert not list((stack.nas / "dumps").glob("*.partial"))
    files = stack.restic("ls", "latest")
    assert "/books.dump" in files
    assert "/caddy-pki/authorities/local/root.key" in files
    # The CA's private keys exist in plain form only inside the encrypted repository.
    assert not stack.staging.exists() or not any(stack.staging.rglob("*.key"))
    assert not any(stack.nas.rglob("*.key"))
    assert (stack.nas / "last-success").read_text().strip()


def test_backup_refuses_when_nas_not_mounted(stack: Stack) -> None:
    (stack.nas / MARKER).unlink()
    try:
        before = sorted(stack.nas.rglob("*"))
        result = stack.run(BACKUP)
        assert result.returncode != 0
        assert "NAS" in result.stderr
        assert sorted(stack.nas.rglob("*")) == before
    finally:
        (stack.nas / MARKER).touch()


def test_backup_removes_dumps_older_than_keep_days(stack: Stack) -> None:
    dumps = stack.nas / "dumps"
    dumps.mkdir(exist_ok=True)
    old, recent = dumps / "books-20200101T000000Z.dump", dumps / "books-recent-test.dump"
    for path, age_days in ((old, 40), (recent, 5)):
        path.write_bytes(b"x")
        stamp = time.time() - age_days * 86400
        os.utime(path, (stamp, stamp))
    _backup(stack)
    assert not old.exists()
    assert recent.exists()
    recent.unlink()


def test_restore_check_restores_into_scratch_database(stack: Stack) -> None:
    _backup(stack)
    result = stack.run(RESTORE, "check")
    assert result.returncode == 0, result.stderr
    assert "app_user 1" in result.stdout
    assert "Restore check passed" in result.stdout
    databases = stack.sql("SELECT datname FROM pg_database").split()
    assert "books_restore_check" not in databases  # cleaned up
    assert stack.sql("SELECT count(*) FROM app_user") == "1"


def test_restore_database_needs_confirmation(stack: Stack) -> None:
    result = stack.run(RESTORE, "database")
    assert result.returncode != 0
    assert "--yes" in result.stderr


def test_restore_database_replaces_live_data(stack: Stack) -> None:
    _backup(stack)
    stack.sql("DELETE FROM user_session; DELETE FROM app_user")
    assert stack.sql("SELECT count(*) FROM app_user") == "0"
    result = stack.run(RESTORE, "database", "--yes")
    assert result.returncode == 0, result.stderr
    assert stack.sql("SELECT count(*) FROM app_user") == "1"


def test_restore_database_from_a_plain_nas_dump(stack: Stack) -> None:
    """Without restic (or its password), the plain dump on the NAS still restores."""
    _backup(stack)
    dump = sorted((stack.nas / "dumps").glob("books-*.dump"))[-1]
    stack.sql("DELETE FROM user_session; DELETE FROM app_user")
    result = stack.run(RESTORE, "database", "--yes", "--dump", str(dump))
    assert result.returncode == 0, result.stderr
    assert stack.sql("SELECT count(*) FROM app_user") == "1"


def test_restore_caddy_ca_brings_back_the_trusted_root(stack: Stack) -> None:
    original = stack.root_fingerprint()
    _backup(stack)
    # Lose the CA: Caddy makes a new one, which no family device would trust.
    stack.compose("exec", "-T", "proxy", "rm", "-rf", "/data/caddy/pki",
                  "/data/caddy/certificates")  # fmt: skip
    stack.compose("restart", "proxy")
    _wait_for_ca(stack)
    assert stack.root_fingerprint() != original
    result = stack.run(RESTORE, "caddy-ca", "--yes")
    assert result.returncode == 0, result.stderr
    _wait_for_ca(stack)
    assert stack.root_fingerprint() == original
    # The certificate Caddy now serves chains to the original root.
    root = stack.staging.parent / "original-root.crt"
    root.write_text(stack.compose("exec", "-T", "proxy", "cat",
                                  "/data/caddy/pki/authorities/local/root.crt").stdout)  # fmt: skip
    for _ in range(30):
        probe = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{ssl_verify_result}", "--cacert", str(root),
             "--resolve", "books.local:443:127.0.0.1", "https://books.local/healthz"],
            capture_output=True, text=True,
        )  # fmt: skip
        if probe.stdout == "0":
            break
        time.sleep(1)
    assert probe.stdout == "0", probe.stderr
