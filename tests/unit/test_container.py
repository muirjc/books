"""The container entrypoint and health check (spec section 10.4, research R12)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = ROOT / "docker" / "entrypoint.sh"


def _stub(bin_dir: Path, name: str, log: Path) -> None:
    script = bin_dir / name
    script.write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\n')
    script.chmod(0o755)


@pytest.fixture
def run_entrypoint(tmp_path: Path) -> object:
    if shutil.which("sh") is None:  # pragma: no cover
        pytest.skip("needs a POSIX shell")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.log"
    for name in ("alembic", "book-tracker", "uvicorn"):
        _stub(bin_dir, name, log)

    def run(**env: str) -> list[str]:
        full_env = {"PATH": f"{bin_dir}:{os.environ['PATH']}", **env}
        subprocess.run(["sh", str(ENTRYPOINT)], env=full_env, check=True)
        return log.read_text().splitlines()

    return run


def test_entrypoint_migrates_then_serves_two_workers(run_entrypoint: object) -> None:
    calls = run_entrypoint()  # type: ignore[operator]
    assert calls[0] == "alembic upgrade head"
    assert len(calls) == 2
    serve = calls[1].split()
    assert serve[:2] == ["uvicorn", "book_tracker.main:app"]
    assert serve[serve.index("--workers") + 1] == "2"
    assert "--proxy-headers" in serve
    # uvicorn's access log records raw paths and query strings; the app logs route
    # templates instead (research R19).
    assert "--no-access-log" in serve


def test_entrypoint_creates_admin_when_configured(run_entrypoint: object) -> None:
    calls = run_entrypoint(BOOK_TRACKER_ADMIN_LOGIN="admin")  # type: ignore[operator]
    assert calls[1] == "book-tracker create-admin --login admin --display-name admin --if-missing"
    assert calls[2].startswith("uvicorn ")


def test_dockerfile_health_check_calls_healthz() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()
    healthcheck = next(line for line in dockerfile.splitlines() if line.startswith("HEALTHCHECK"))
    assert "http://127.0.0.1:8000/healthz" in dockerfile[dockerfile.index(healthcheck) :]
