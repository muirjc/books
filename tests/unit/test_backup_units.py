"""The nightly backup's systemd units (spec section 10.6; deploy/pi/README.md section 10)."""

from __future__ import annotations

import configparser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKUP = ROOT / "deploy" / "pi" / "backup"


def _unit(name: str) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str  # type: ignore[assignment,method-assign]  # keep key case
    parser.read(BACKUP / name)
    return parser


def test_service_gives_restic_a_cache_directory() -> None:
    """systemd runs the service without $HOME, so restic needs an explicit cache directory."""
    service = _unit("books-backup.service")["Service"]
    assert service["CacheDirectory"] == "books-backup"
    assert "RESTIC_CACHE_DIR=/var/cache/books-backup" in service["Environment"]


def test_timer_runs_nightly_and_catches_up() -> None:
    timer = _unit("books-backup.timer")["Timer"]
    assert timer["OnCalendar"] == "*-*-* 02:30"
    assert timer["Persistent"] == "true"
