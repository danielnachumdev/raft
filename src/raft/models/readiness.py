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


def _optional_positive_float(
    raw: Any,
    *,
    path: Path,
    field: str,
) -> Optional[float]:
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path}: readiness.{field} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{path}: readiness.{field} must be > 0")
    return value


def _optional_positive_int(
    raw: Any,
    *,
    path: Path,
    field: str,
) -> Optional[int]:
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path}: readiness.{field} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{path}: readiness.{field} must be > 0")
    return value


def _timing_from_raw(raw: dict[str, Any], path: Path) -> dict[str, Any]:
    start = _optional_positive_float(
        raw.get("startPeriodSeconds", raw.get("start_period_seconds")),
        path=path,
        field="startPeriodSeconds",
    )
    interval = _optional_positive_float(
        raw.get("intervalSeconds", raw.get("interval_seconds")),
        path=path,
        field="intervalSeconds",
    )
    probe_timeout = _optional_positive_float(
        raw.get("probeTimeoutSeconds", raw.get("probe_timeout_seconds")),
        path=path,
        field="probeTimeoutSeconds",
    )
    retries = _optional_positive_int(
        raw.get("retries"),
        path=path,
        field="retries",
    )
    timeout = _optional_positive_float(
        raw.get("timeoutSeconds", raw.get("timeout_seconds")),
        path=path,
        field="timeoutSeconds",
    )

    start_period_seconds = (
        start if start is not None else DEFAULT_START_PERIOD_SECONDS
    )
    interval_seconds = (
        interval if interval is not None else DEFAULT_INTERVAL_SECONDS
    )
    probe_timeout_seconds = (
        probe_timeout if probe_timeout is not None else DEFAULT_PROBE_TIMEOUT_SECONDS
    )
    retries_n = retries if retries is not None else DEFAULT_RETRIES
    if timeout is None:
        timeout_seconds = default_timeout_seconds(
            start_period_seconds=start_period_seconds,
            interval_seconds=interval_seconds,
            retries=retries_n,
        )
    else:
        timeout_seconds = timeout
        if timeout_seconds <= start_period_seconds:
            raise ValueError(
                f"{path}: readiness.timeoutSeconds ({timeout_seconds:g}) must be "
                f"greater than startPeriodSeconds ({start_period_seconds:g})"
            )
        # Explicit budgets only need room for start_period + one probe.
        # (Auto-default still uses the full retries×interval + buffer floor.)
        min_useful = start_period_seconds + interval_seconds
        if timeout_seconds < min_useful:
            raise ValueError(
                f"{path}: readiness.timeoutSeconds ({timeout_seconds:g}) must be "
                f"at least startPeriodSeconds + intervalSeconds "
                f"({min_useful:g}s)"
            )

    return {
        "timeout_seconds": timeout_seconds,
        "start_period_seconds": start_period_seconds,
        "interval_seconds": interval_seconds,
        "probe_timeout_seconds": probe_timeout_seconds,
        "retries": retries_n,
    }


def parse_readiness(
    spec: dict[str, Any],
    ports: tuple[PortSpec, ...],
    path: Path,
) -> ReadinessSpec:
    if "readinessProbe" in spec:
        raise ValueError(f"{path}: readinessProbe is not supported; use spec.readiness")
    raw = spec.get("readiness")
    if raw is None:
        http_ports = [p for p in ports if p.expose == "http"]
        timing = _timing_from_raw({}, path)
        if http_ports:
            return ReadinessSpec(
                type="http",
                port=http_ports[0].name,
                path="/",
                **timing,
            )
        return ReadinessSpec(
            type="tcp",
            port=ports[0].name if ports else None,
            **timing,
        )
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: spec.readiness must be an object")
    rtype = str(raw.get("type", "http")).strip().lower() or "http"
    if rtype not in READINESS_TYPES:
        raise ValueError(
            f"{path}: readiness.type must be one of {sorted(READINESS_TYPES)}, "
            f"got {rtype!r}"
        )
    port_name = raw.get("port")
    port_s = str(port_name).strip() if port_name is not None else None
    if port_s == "":
        port_s = None
    path_raw = raw.get("path", "/")
    probe_path = str(path_raw).strip() or "/"
    if not probe_path.startswith("/"):
        probe_path = f"/{probe_path}"
    timing = _timing_from_raw(raw, path)
    readiness = ReadinessSpec(
        type=rtype,
        port=port_s,
        path=probe_path,
        **timing,
    )
    if rtype != "none":
        try:
            resolved = readiness.resolve_port(ports)
        except KeyError as exc:
            raise ValueError(f"{path}: {exc}") from exc
        if resolved is None:
            raise ValueError(f"{path}: readiness requires a named port")
        if rtype == "http" and resolved.expose != "http":
            raise ValueError(
                f"{path}: readiness.type=http requires an expose=http port "
                f"(got {resolved.name!r} expose={resolved.expose!r})"
            )
        if readiness.port is None:
            readiness = ReadinessSpec(
                type=rtype,
                port=resolved.name,
                path=probe_path,
                **timing,
            )
    return readiness
