"""App readiness: how raft decides an app (or cutover target) is live."""

from dataclasses import dataclass
from typing import Optional

from .ports import PortSpec
from .readiness_timing import (
    DEFAULT_INTERVAL_SECONDS,
    DEFAULT_PROBE_TIMEOUT_SECONDS,
    DEFAULT_RETRIES,
    DEFAULT_START_PERIOD_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    ReadinessTiming,
)

READINESS_TYPES = frozenset({"http", "tcp", "none"})


@dataclass(frozen=True)
class ReadinessSpec:
    type: str = "http"
    port: Optional[str] = None
    path: str = "/"
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    start_period_seconds: float = DEFAULT_START_PERIOD_SECONDS
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS
    probe_timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS
    retries: int = DEFAULT_RETRIES

    def resolve_port(self, ports: tuple[PortSpec, ...]) -> Optional[PortSpec]:
        if self.type == "none":
            return None
        if self.port:
            for port in ports:
                if port.name == self.port:
                    return port
            known = ", ".join(p.name for p in ports) or "(none)"
            raise KeyError(f"readiness.port {self.port!r} not in ports (known: {known})")
        if self.type == "http":
            for port in ports:
                if port.expose == "http":
                    return port
        if ports:
            return ports[0]
        return None

    def timing_summary(self) -> str:
        """Short operator-facing timing line for timeout CTAs."""
        fmt = ReadinessTiming.format_duration_seconds
        return (
            f"timeoutSeconds={fmt(self.timeout_seconds)}, "
            f"startPeriodSeconds={fmt(self.start_period_seconds)}, "
            f"interval={fmt(self.interval_seconds)}, "
            f"retries={self.retries}"
        )
