"""App readiness: how raft decides an app (or cutover target) is live."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .ports import PortSpec

READINESS_TYPES = frozenset({"http", "tcp", "none"})

# Compose healthcheck defaults (cold start / migrations need a long start_period).
DEFAULT_START_PERIOD_SECONDS = 45.0
DEFAULT_INTERVAL_SECONDS = 2.0
DEFAULT_PROBE_TIMEOUT_SECONDS = 2.0
DEFAULT_RETRIES = 15
# Extra seconds after start_period + probe budget so raft does not race Compose.
_TIMEOUT_BUFFER_SECONDS = 15.0
# Floor for the raft wait budget when the formula would be lower.
DEFAULT_TIMEOUT_SECONDS = 120.0


def recommended_timeout_seconds(
    *,
    start_period_seconds: float = DEFAULT_START_PERIOD_SECONDS,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    retries: int = DEFAULT_RETRIES,
) -> float:
    """Minimum wait that covers Compose start_period plus probe retries."""
    return (
        float(start_period_seconds)
        + float(retries) * float(interval_seconds)
        + _TIMEOUT_BUFFER_SECONDS
    )


def default_timeout_seconds(
    *,
    start_period_seconds: float = DEFAULT_START_PERIOD_SECONDS,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    retries: int = DEFAULT_RETRIES,
) -> float:
    """Default raft wait: at least 120s, and never below the Compose probe budget."""
    return max(
        DEFAULT_TIMEOUT_SECONDS,
        recommended_timeout_seconds(
            start_period_seconds=start_period_seconds,
            interval_seconds=interval_seconds,
            retries=retries,
        ),
    )


def format_duration_seconds(seconds: float) -> str:
    """Compose-friendly duration (``45s``, ``2.5s``)."""
    value = float(seconds)
    if value == int(value):
        return f"{int(value)}s"
    return f"{value:g}s"


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
        return (
            f"timeoutSeconds={format_duration_seconds(self.timeout_seconds)}, "
            f"startPeriodSeconds={format_duration_seconds(self.start_period_seconds)}, "
            f"interval={format_duration_seconds(self.interval_seconds)}, "
            f"retries={self.retries}"
        )
