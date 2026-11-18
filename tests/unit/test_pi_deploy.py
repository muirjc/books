"""The Raspberry Pi Compose stack and Caddy config (spec sections 10.3-10.5).

These check the network boundaries spec 10.3 relies on, because Docker-published ports
bypass ufw: only Caddy publishes ports, bound to the Pi's LAN address; the app and
PostgreSQL are never published, and PostgreSQL has no route out.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy" / "pi"
LAN_IP = "192.168.4.10"

pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None
    or subprocess.run(["docker", "compose", "version"], capture_output=True).returncode != 0,
    reason="needs docker compose",
)


@pytest.fixture(scope="module")
def config(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """The stack as Compose resolves it, with the example .env's values filled in."""
    env = tmp_path_factory.mktemp("env") / ".env"
    example = (DEPLOY / ".env.example").read_text()
    env.write_text(
        example.replace("PI_LAN_IP=", f"PI_LAN_IP={LAN_IP}", 1)
        .replace("POSTGRES_PASSWORD=", "POSTGRES_PASSWORD=" + "a" * 64, 1)
        .replace("BOOK_TRACKER_SECRET_KEY=", "BOOK_TRACKER_SECRET_KEY=" + "b" * 64, 1)
    )
    result = subprocess.run(
        ["docker", "compose", "--env-file", str(env), "config", "--format", "json"],
        cwd=DEPLOY,
        capture_output=True,
        text=True,
        check=True,
    )
    parsed: dict[str, Any] = json.loads(result.stdout)
    return parsed


def test_three_services_restart_unless_stopped(config: dict[str, Any]) -> None:
    services = config["services"]
    assert set(services) == {"proxy", "app", "db"}
    for name, service in services.items():
        assert service["restart"] == "unless-stopped", name


def test_only_proxy_publishes_ports_on_the_lan_address(config: dict[str, Any]) -> None:
    services = config["services"]
    assert "ports" not in services["app"]
    assert "ports" not in services["db"]
    published = {(p["host_ip"], p["published"], p["target"]) for p in services["proxy"]["ports"]}
    assert published == {(LAN_IP, "80", 80), (LAN_IP, "443", 443)}


def test_database_is_on_an_internal_network_only(config: dict[str, Any]) -> None:
    services = config["services"]
    assert set(services["db"]["networks"]) == {"backend"}
    assert config["networks"]["backend"]["internal"] is True
    assert "backend" not in services["proxy"]["networks"]
    assert set(services["app"]["networks"]) == {"edge", "backend"}


def test_app_runs_the_published_image_in_production(config: dict[str, Any]) -> None:
    app = config["services"]["app"]
    assert app["image"] == "ghcr.io/muirjc/books:latest"
    env = app["environment"]
    assert env["BOOK_TRACKER_ENVIRONMENT"] == "production"
    assert env["BOOK_TRACKER_DATABASE_URL"] == f"postgresql://books:{'a' * 64}@db:5432/books"
    assert env["BOOK_TRACKER_SECRET_KEY"] == "b" * 64
    assert app["depends_on"]["db"]["condition"] == "service_healthy"
    # The image's HEALTHCHECK calls /healthz; Compose must not switch it off.
    assert not app.get("healthcheck", {}).get("disable", False)


def test_database_has_health_check_and_data_on_the_host(config: dict[str, Any]) -> None:
    db = config["services"]["db"]
    assert db["image"].startswith("postgres:16")
    assert "pg_isready" in " ".join(db["healthcheck"]["test"])
    data = [v for v in db["volumes"] if v["target"] == "/var/lib/postgresql/data"]
    assert data and data[0]["type"] == "bind"
    assert data[0]["source"] == "/srv/books/postgres"


def test_proxy_keeps_its_ca_in_a_named_volume(config: dict[str, Any]) -> None:
    proxy = config["services"]["proxy"]
    data = [v for v in proxy["volumes"] if v["target"] == "/data"]
    assert data and data[0]["type"] == "volume"
    assert proxy["depends_on"]["app"]["condition"] == "service_healthy"


def test_missing_secret_fails_loudly(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(f"PI_LAN_IP={LAN_IP}\nPOSTGRES_PASSWORD=x\n")
    result = subprocess.run(
        ["docker", "compose", "--env-file", str(env), "config"],
        cwd=DEPLOY,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "BOOK_TRACKER_SECRET_KEY" in result.stderr


def test_example_env_is_committed_but_real_env_is_ignored() -> None:
    assert (DEPLOY / ".env.example").is_file()
    ignored = subprocess.run(["git", "check-ignore", "-q", "deploy/pi/.env"], cwd=ROOT).returncode
    tracked = subprocess.run(
        ["git", "check-ignore", "-q", "deploy/pi/.env.example"], cwd=ROOT
    ).returncode
    assert ignored == 0
    assert tracked == 1


def test_caddyfile_uses_internal_ca_for_books_local() -> None:
    caddyfile = (DEPLOY / "caddy" / "Caddyfile").read_text()
    assert "tls internal" in caddyfile
    assert "books.local, {$PI_LAN_IP}" in caddyfile
    # Connections by IP carry no SNI; without this they fail the TLS handshake.
    assert "default_sni {$PI_LAN_IP}" in caddyfile
    assert "reverse_proxy app:8000" in caddyfile


def test_caddyfile_is_valid(config: dict[str, Any]) -> None:
    image = config["services"]["proxy"]["image"]
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-e",
            f"PI_LAN_IP={LAN_IP}",
            "-v",
            f"{DEPLOY / 'caddy'}:/etc/caddy:ro",
            image,
            "caddy",
            "validate",
            "--config",
            "/etc/caddy/Caddyfile",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_caddy_config_mounted_as_a_directory(config: dict[str, Any]) -> None:
    """A single-file bind mount goes stale when an editor replaces the file."""
    mounts = {v["target"]: v for v in config["services"]["proxy"]["volumes"]}
    assert mounts["/etc/caddy"]["type"] == "bind"
    assert mounts["/etc/caddy"]["source"] == str(DEPLOY / "caddy")
    assert mounts["/etc/caddy"]["read_only"] is True
