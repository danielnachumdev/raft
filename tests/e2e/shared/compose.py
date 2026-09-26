"""Docker Compose helpers for e2e — strict teardown, apps-only projects."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Optional

import yaml

from raft.models.app import ROUTER_COMPOSE_ID
from tests.shared.artifacts import GeneratedArtifacts
from tests.shared.wait import Wait


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(
            ["docker", "info"],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False


def new_project_name() -> str:
    return f"raft-e2e-{uuid.uuid4().hex[:12]}"


def apps_only_compose(generated: Path, dest: Path) -> Path:
    """Write compose with only App services (drop router stub; drop healthchecks)."""
    raw = GeneratedArtifacts(generated).compose_apps()
    services = _strip_router_and_health(dict(raw.get("services") or {}))
    dest.write_text(yaml.safe_dump({"services": services}, sort_keys=False), encoding="utf-8")
    return dest


def _strip_router_and_health(services: dict) -> dict:
    services.pop("router", None)
    services.pop(ROUTER_COMPOSE_ID, None)
    for name, svc in list(services.items()):
        if not isinstance(svc, dict):
            continue
        svc = dict(svc)
        svc.pop("healthcheck", None)
        services[name] = _publish_exposed_ports(svc)
    return services


def _publish_exposed_ports(svc: dict) -> dict:
    expose = svc.get("expose") or []
    existing_ports = list(svc.get("ports") or [])
    for port in expose:
        mapping = f"127.0.0.1::{port}"
        if mapping not in existing_ports and not any(
            str(p).endswith(f":{port}") for p in existing_ports
        ):
            existing_ports.append(mapping)
    if existing_ports:
        svc["ports"] = existing_ports
    return svc


class ComposeProject:
    """One docker compose project with guaranteed teardown."""

    def __init__(self, project: str, compose_file: Path, workdir: Path) -> None:
        self.project = project
        self.compose_file = compose_file
        self.workdir = workdir

    def _cmd(self, *args: str) -> list[str]:
        return [
            "docker",
            "compose",
            "-p",
            self.project,
            "-f",
            str(self.compose_file),
            *args,
        ]

    def up(self) -> None:
        proc = subprocess.run(
            self._cmd("up", "-d", "--pull", "missing"),
            check=False,
            cwd=self.workdir,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"compose up failed ({self.project}):\n" f"{proc.stdout}\n{proc.stderr}"
            )

    def down(self) -> None:
        subprocess.run(
            self._cmd("down", "-v", "--remove-orphans"),
            check=False,
            cwd=self.workdir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self._force_remove_labeled()

    def _force_remove_labeled(self) -> None:
        labeled = subprocess.run(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                f"label=com.docker.compose.project={self.project}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        ids = [x for x in labeled.stdout.split() if x]
        if ids:
            subprocess.run(["docker", "rm", "-f", *ids], check=False, capture_output=True)

    def ps_json(self) -> list[dict[str, Any]]:
        proc = subprocess.run(
            self._cmd("ps", "--format", "json"),
            check=True,
            cwd=self.workdir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        if not lines:
            return []
        # Compose v2 may emit one JSON object per line or a JSON array.
        if lines[0].lstrip().startswith("["):
            data = json.loads("".join(lines))
            assert isinstance(data, list)
            return data
        return [json.loads(ln) for ln in lines]

    def service_running(self, service: str) -> bool:
        for row in self.ps_json():
            name = row.get("Service") or row.get("Name") or ""
            state = (row.get("State") or row.get("Status") or "").lower()
            if service in str(name) and ("running" in state or state == "up"):
                return True
        return False

    def published_port(self, service: str, container_port: int) -> Optional[int]:
        proc = subprocess.run(
            self._cmd("port", service, str(container_port)),
            check=False,
            cwd=self.workdir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        # e.g. 127.0.0.1:32768
        hostport = proc.stdout.strip().rsplit(":", 1)[-1]
        try:
            return int(hostport)
        except ValueError:
            return None

    def wait_running(self, service: str, *, timeout: float = 60.0) -> None:
        Wait.until(
            lambda: self.service_running(service),
            timeout=timeout,
            interval=0.5,
            message=f"service {service!r} not running in project {self.project}",
        )
