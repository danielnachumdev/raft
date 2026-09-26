"""Compose/container log and health diagnostics for operator CTAs."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Optional, Sequence

from raft.errors import (
    OperatorError,
    append_diagnostics,
    compose_services_from_failure_text,
    format_service_log_block,
    join_diagnostic_blocks,
    prefer_errorish_lines,
    summarize_health_inspect,
)

from ...models.stack import Stack
from ..shell import Shell

if TYPE_CHECKING:
    from .stack import DockerStack

logger = logging.getLogger(__name__)

DIAG_LOG_TAIL = 40
DIAG_MAX_LINES = 16


class ComposeDiagnostics:
    """Build readable log/health blocks for Compose services and containers."""

    def __init__(self, stack: Stack, shell: Shell, docker: "DockerStack") -> None:
        self.stack = stack
        self.sh = shell
        self._docker = docker

    def compose_logs(self, *services: str, tail: int = DIAG_LOG_TAIL) -> str:
        """Tail recent Compose logs for ``services`` (declarative log relay)."""
        names = [s for s in services if s]
        if not names:
            return ""
        result = self.sh.compose(
            "logs",
            "--no-color",
            "--tail",
            str(tail),
            *names,
            capture=True,
            check=False,
        )
        return (result.stdout or result.stderr or "").strip()

    def container_logs(self, name: str, *, tail: int = DIAG_LOG_TAIL) -> str:
        """Tail logs for a named container (e.g. cutover ``_tmp``)."""
        if not name:
            return ""
        result = self.sh.docker(
            "logs",
            "--tail",
            str(tail),
            name,
            capture=True,
            check=False,
        )
        return (result.stderr or result.stdout or "").strip()

    def service_health_summary(self, service: str) -> str:
        """Short status/health (+ last healthcheck output when present)."""
        cid = self._docker.try_service_container_id(service)
        if not cid:
            return "absent"
        state = self._inspect_state(cid)
        if state is None:
            return "unknown"
        return self._summarize_state(state)

    def not_ready_services(self, services: Optional[list[str]] = None) -> list[str]:
        """Compose services that are missing, exited, or unhealthy."""
        names = services if services is not None else list(self.stack.core_services)
        return [name for name in names if not self._docker.service_is_ready(name)]

    def diagnostics_for(
        self,
        *services: str,
        containers: Sequence[str] = (),
        tail: int = DIAG_LOG_TAIL,
        max_lines: int = DIAG_MAX_LINES,
    ) -> str:
        """Readable log/health blocks for Compose services and/or containers."""
        blocks = [self._service_block(s, tail=tail, max_lines=max_lines) for s in services if s]
        blocks.extend(
            self._container_block(n, tail=tail, max_lines=max_lines) for n in containers if n
        )
        return join_diagnostic_blocks(*blocks)

    def enrich_compose_failure(
        self,
        exc: OperatorError,
        *,
        services: Optional[Sequence[str]] = None,
        detail: str = "",
    ) -> OperatorError:
        """Append recent logs for unhealthy/exited services to a compose CTA."""
        blob = str(exc)
        ordered = self._failure_targets(blob, detail=detail, services=services)
        if not ordered:
            return exc
        diagnostics = self._docker.diagnostics_for(*ordered)
        if not diagnostics:
            return exc
        return OperatorError(
            append_diagnostics(blob, diagnostics),
            has_fix=exc.has_fix,
        )

    def _inspect_state(self, container_id: str) -> Optional[dict[str, Any]]:
        result = self.sh.docker(
            "inspect",
            "--format",
            "{{json .State}}",
            container_id,
            capture=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        try:
            state = json.loads((result.stdout or "").strip())
        except json.JSONDecodeError:
            return None
        return state if isinstance(state, dict) else None

    @staticmethod
    def _summarize_state(state: dict[str, Any]) -> str:
        status = str(state.get("Status") or "unknown")
        health_obj = state.get("Health")
        health = "none"
        last_out = ""
        if isinstance(health_obj, dict):
            health = str(health_obj.get("Status") or "none")
            last_out = ComposeDiagnostics._last_health_output(health_obj)
        return summarize_health_inspect(status, health, last_output=last_out)

    @staticmethod
    def _last_health_output(health_obj: dict[str, Any]) -> str:
        log = health_obj.get("Log")
        if not isinstance(log, list) or not log:
            return ""
        last = log[-1]
        if not isinstance(last, dict):
            return ""
        return str(last.get("Output") or "")

    def _service_block(self, service: str, *, tail: int, max_lines: int) -> str:
        logs = prefer_errorish_lines(self.compose_logs(service, tail=tail), max_lines=max_lines)
        return format_service_log_block(
            service,
            logs,
            health=self.service_health_summary(service),
            max_lines=max_lines,
        )

    def _container_block(self, name: str, *, tail: int, max_lines: int) -> str:
        logs = prefer_errorish_lines(self.container_logs(name, tail=tail), max_lines=max_lines)
        return format_service_log_block(name, logs, health="container", max_lines=max_lines)

    def _failure_targets(
        self,
        blob: str,
        *,
        detail: str,
        services: Optional[Sequence[str]],
    ) -> list[str]:
        mentioned = compose_services_from_failure_text(
            f"{blob}\n{detail}",
            known_services=list(self.stack.core_services),
        )
        targets: list[str] = []
        if services:
            targets.extend(services)
        targets.extend(mentioned)
        if not targets:
            targets = self._docker.not_ready_services()
        return self._unique_names(targets)

    @staticmethod
    def _unique_names(names: Sequence[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for name in names:
            if name and name not in seen:
                seen.add(name)
                ordered.append(name)
        return ordered
