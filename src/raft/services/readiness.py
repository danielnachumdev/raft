"""Compose healthchecks and runtime readiness waits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ..adapters.http import HttpProbe
from ..models.app import App
from ..models.manifest import AppSpec
from ..models.ports import PortSpec
from ..models.readiness_spec import (
    DEFAULT_INTERVAL_SECONDS,
    DEFAULT_PROBE_TIMEOUT_SECONDS,
    DEFAULT_RETRIES,
    DEFAULT_START_PERIOD_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    format_duration_seconds,
)
from ..models.stack import Stack


@dataclass(frozen=True)
class ReadinessStrategy:
    kind: str
    port: Optional[PortSpec] = None
    path: str = "/"
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    start_period_seconds: float = DEFAULT_START_PERIOD_SECONDS
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS
    probe_timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS
    retries: int = DEFAULT_RETRIES

    @classmethod
    def from_spec(cls, spec: AppSpec) -> "ReadinessStrategy":
        readiness = spec.readiness
        timing = cls._timing_kwargs(readiness)
        if readiness.type == "none":
            return cls(kind="none", **timing)
        return cls(
            kind=readiness.type,
            port=readiness.resolve_port(spec.ports),
            path=readiness.path,
            **timing,
        )

    @staticmethod
    def _timing_kwargs(readiness) -> dict:
        return {
            "timeout_seconds": readiness.timeout_seconds,
            "start_period_seconds": readiness.start_period_seconds,
            "interval_seconds": readiness.interval_seconds,
            "probe_timeout_seconds": readiness.probe_timeout_seconds,
            "retries": readiness.retries,
        }

    def healthcheck_test(self) -> Optional[list[str]]:
        if self.kind == "none" or self.port is None:
            return None
        if self.kind == "http":
            path = self.path if self.path.startswith("/") else f"/{self.path}"
            return [
                "CMD",
                "wget",
                "-qO-",
                f"http://127.0.0.1:{self.port.container_port}{path}",
            ]
        if self.kind == "tcp":
            return [
                "CMD-SHELL",
                f"nc -z 127.0.0.1 {self.port.container_port} || exit 1",
            ]
        raise ValueError(f"unknown readiness kind {self.kind!r}")

    def healthcheck_compose_lines(self) -> list[str]:
        """Compose ``healthcheck:`` block lines (indented under the service)."""
        test = self.healthcheck_test()
        if test is None:
            return []
        quoted = ", ".join(f'"{part}"' for part in test)
        return [
            "    healthcheck:",
            f"      test: [{quoted}]",
            f"      interval: {format_duration_seconds(self.interval_seconds)}",
            f"      timeout: {format_duration_seconds(self.probe_timeout_seconds)}",
            f"      retries: {self.retries}",
            # Cold start (e.g. Alembic) often exceeds a few seconds; keep
            # health "starting" long enough for cutover TCP waits.
            f"      start_period: {format_duration_seconds(self.start_period_seconds)}",
        ]

    def timing_summary(self) -> str:
        return (
            f"timeoutSeconds={format_duration_seconds(self.timeout_seconds)}, "
            f"startPeriodSeconds={format_duration_seconds(self.start_period_seconds)}, "
            f"interval={format_duration_seconds(self.interval_seconds)}, "
            f"retries={self.retries}"
        )

    def wait_predicate(
        self,
        app: App,
        stack: Stack,
        http: HttpProbe,
        *,
        tcp_ok: Optional[Callable[[int], bool]] = None,
        compose_ready: Optional[Callable[[], bool]] = None,
    ) -> Optional[Callable[[], bool]]:
        if self.kind == "none":
            return None
        if self.kind == "http":
            return lambda: http.public_host_ok(app)
        if self.kind == "tcp":
            assert self.port is not None
            # Internal-only ports are not published on the host — wait on Compose
            # health/running instead of probing 127.0.0.1:<containerPort>.
            if self.port.expose == "none":
                if compose_ready is not None:
                    return compose_ready
                if tcp_ok is not None:
                    return lambda: tcp_ok(self.port.container_port)
                return lambda: False
            port_num = self.port.public_port or self.port.container_port
            if tcp_ok is not None:
                return lambda: tcp_ok(port_num)
            return lambda: http.tcp_port_ok(port_num)
        raise ValueError(f"unknown readiness kind {self.kind!r}")
