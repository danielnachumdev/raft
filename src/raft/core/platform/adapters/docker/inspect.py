"""Container inspect, stats, and readiness probes for Compose services."""

import logging
import subprocess
from typing import Any, Dict, List, Optional

from raft.core.core.errors.checked import CheckedCommands
from raft.core.core.errors.cta import OperatorError
from raft.core.core.errors.domain import DomainErrors
from raft.core.core.models.stack import Stack
from ..shell import Shell
from .inspect_runtime import InspectRuntime

logger = logging.getLogger(__name__)

_STATUS_HEALTH_FMT = (
    "{{.State.Status}} " "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}"
)


class DockerInspect:
    """Container ids, stats, runtime, and readiness via Engine inspect."""

    stack: Stack
    sh: Shell

    def gate_published_ports(self) -> List[int]:
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
    def _parse_published_ports(stdout: str) -> List[int]:
        ports: List[int] = []
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
            CheckedCommands.raise_for_compose_failure(exc, action=f"inspect service {service}")
        cid = (result.stdout or "").strip()
        if not cid:
            raise DomainErrors.service_not_running(service)
        return cid

    def try_service_container_id(self, service: str) -> Optional[str]:
        """Return the running container id for ``service``, or ``None`` if absent."""
        result = self.sh.compose("ps", "-q", service, capture=True, check=False)
        if result.returncode != 0:
            return None
        cid = (result.stdout or "").strip()
        return cid or None

    def containers_stats(self, container_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """One-shot ``docker stats --no-stream`` keyed by container id."""
        if not container_ids:
            return {}
        stdout = self._docker_stats_stdout(container_ids)
        if stdout is None:
            return {}
        return InspectRuntime.index_stats_rows(stdout, container_ids)

    def _docker_stats_stdout(self, container_ids: List[str]) -> Optional[str]:
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

    def container_inspect_runtime(self, container_id: str) -> Optional[Dict[str, Any]]:
        """Status, health, start time, and HostConfig limits for one container.

        JSON inspect avoids a Docker Go-template bug: mixing ``.State.Health``
        with ``.HostConfig.*`` fails when the container has no healthcheck
        (nginx edge), which surfaced as STATUS ``unknown`` in ``raft status``.
        """
        result = self.sh.docker(
            "inspect",
            "--format",
            "{{json .}}",
            container_id,
            capture=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return InspectRuntime.from_inspect_json(result.stdout or "")

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

    def service_runtime(self, service: str) -> tuple:
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
    def _runtime_status_health(stdout: str) -> tuple:
        parts = stdout.strip().split()
        if not parts:
            return ("missing", "none")
        status = parts[0]
        health = parts[1] if len(parts) > 1 else "none"
        return (status, health)
