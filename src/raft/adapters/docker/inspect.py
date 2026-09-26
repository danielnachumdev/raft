"""Container inspect, stats, and readiness probes for Compose services."""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any, Optional

from raft.errors import (
    OperatorError,
    raise_for_compose_failure,
    service_not_running,
)

from ...models.stack import Stack
from ..shell import Shell

logger = logging.getLogger(__name__)

_STATUS_HEALTH_FMT = (
    "{{.State.Status}} "
    "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}"
)


class DockerInspect:
    """Mixin: container ids, stats, runtime, image refs, published ports."""

    stack: Stack
    sh: Shell

    def gate_published_ports(self) -> list[int]:
        try:
            cid = self.service_container_id(self.stack.gate)
        except RuntimeError:
            return []
        result = self.sh.docker(
            "inspect",
            "-f",
            "{{range $p, $conf := .NetworkSettings.Ports}}" "{{if $conf}}{{$p}} {{end}}{{end}}",
            cid,
            capture=True,
            check=False,
        )
        if result.returncode != 0:
            return []
        return self._parse_published_ports(result.stdout or "")

    @staticmethod
    def _parse_published_ports(stdout: str) -> list[int]:
        ports: list[int] = []
        for token in stdout.split():
            num = token.split("/", 1)[0]
            if num.isdigit():
                ports.append(int(num))
        return sorted(set(ports))

    def service_container_id(self, service: str) -> str:
        result = self.sh.compose("ps", "-q", service, capture=True, check=False)
        if result.returncode != 0:
            exc = subprocess.CalledProcessError(
                result.returncode,
                ["docker", "compose", "ps", "-q", service],
                output=result.stdout,
                stderr=(result.stderr or "").strip(),
            )
            raise_for_compose_failure(exc, action=f"inspect service {service}")
        cid = (result.stdout or "").strip()
        if not cid:
            raise service_not_running(service)
        return cid

    def try_service_container_id(self, service: str) -> Optional[str]:
        """Return the running container id for ``service``, or ``None`` if absent."""
        result = self.sh.compose("ps", "-q", service, capture=True, check=False)
        if result.returncode != 0:
            return None
        cid = (result.stdout or "").strip()
        return cid or None

    def containers_stats(self, container_ids: list[str]) -> dict[str, dict[str, Any]]:
        """One-shot ``docker stats --no-stream`` keyed by container id."""
        if not container_ids:
            return {}
        stdout = self._docker_stats_stdout(container_ids)
        if stdout is None:
            return {}
        return self._index_stats_rows(stdout, container_ids)

    def _docker_stats_stdout(self, container_ids: list[str]) -> Optional[str]:
        result = self.sh.docker(
            "stats",
            "--no-stream",
            "--format",
            "{{json .}}",
            *container_ids,
            capture=True,
            check=False,
        )
        if result.returncode != 0:
            logger.debug(
                "docker stats failed rc=%s: %s",
                result.returncode,
                (result.stderr or "").strip(),
            )
            return None
        return result.stdout or ""

    @staticmethod
    def _index_stats_rows(
        stdout: str, container_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            row = DockerInspect._parse_stats_line(line)
            if row is None:
                continue
            raw_id = str(row.get("ID") or row.get("Container") or "").strip()
            if not raw_id:
                continue
            by_id[raw_id] = row
            for cid in container_ids:
                if cid.startswith(raw_id) or raw_id.startswith(cid):
                    by_id[cid] = row
        return by_id

    @staticmethod
    def _parse_stats_line(line: str) -> Optional[dict[str, Any]]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("skip unparseable docker stats line: %r", line)
            return None
        return row if isinstance(row, dict) else None

    def container_inspect_runtime(self, container_id: str) -> Optional[dict[str, Any]]:
        """Status, start time, and HostConfig resource limits for one container."""
        result = self.sh.docker(
            "inspect",
            "-f",
            "{{.State.Status}}|{{.State.StartedAt}}|"
            "{{.HostConfig.NanoCpus}}|{{.HostConfig.Memory}}",
            container_id,
            capture=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        parts = (result.stdout or "").strip().split("|")
        if len(parts) < 4:
            return None
        return self._runtime_from_parts(parts)

    @staticmethod
    def _runtime_from_parts(parts: list[str]) -> dict[str, Any]:
        status, started_at, nano_raw, mem_raw = parts[0], parts[1], parts[2], parts[3]
        return {
            "status": status or "unknown",
            "started_at": started_at or "",
            "nano_cpus": int(nano_raw) if nano_raw.isdigit() else None,
            "memory_bytes": int(mem_raw) if mem_raw.isdigit() else None,
        }

    def service_is_ready(self, service: str) -> bool:
        """True when running and healthy (or no healthcheck); for expose:none."""
        stdout = self._inspect_status_health(service)
        if stdout is None:
            return False
        ready = self._ready_from_inspect(stdout)
        logger.debug("service_is_ready %s -> %s", service, ready)
        return ready

    @staticmethod
    def _ready_from_inspect(stdout: str) -> bool:
        parts = stdout.strip().split()
        if not parts or parts[0] != "running":
            return False
        health = parts[1] if len(parts) > 1 else "none"
        return health in ("none", "healthy")

    def service_runtime(self, service: str) -> tuple[str, str]:
        """Return ``(status, health)`` for a Compose service (``missing`` if absent)."""
        stdout = self._inspect_status_health(service)
        if stdout is None:
            return ("missing", "none")
        return self._runtime_status_health(stdout)

    def _inspect_status_health(self, service: str) -> Optional[str]:
        try:
            cid = self.service_container_id(service)
        except OperatorError:
            return None
        result = self.sh.docker(
            "inspect",
            "-f",
            _STATUS_HEALTH_FMT,
            cid,
            capture=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout or ""

    @staticmethod
    def _runtime_status_health(stdout: str) -> tuple[str, str]:
        parts = stdout.strip().split()
        if not parts:
            return ("missing", "none")
        status = parts[0]
        health = parts[1] if len(parts) > 1 else "none"
        return (status, health)

