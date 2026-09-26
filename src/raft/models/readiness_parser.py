"""Parse ``spec.readiness`` into a validated ReadinessSpec."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .ports import PortSpec
from .readiness_spec import (
    DEFAULT_INTERVAL_SECONDS,
    DEFAULT_PROBE_TIMEOUT_SECONDS,
    DEFAULT_RETRIES,
    DEFAULT_START_PERIOD_SECONDS,
    READINESS_TYPES,
    ReadinessSpec,
    default_timeout_seconds,
)


class ReadinessParser:
    """Parse ``spec.readiness`` into a validated :class:`ReadinessSpec`."""

    def parse(
        self,
        spec: dict[str, Any],
        ports: tuple[PortSpec, ...],
        path: Path,
    ) -> ReadinessSpec:
        if "readinessProbe" in spec:
            raise ValueError(f"{path}: readinessProbe is not supported; use spec.readiness")
        raw = spec.get("readiness")
        if raw is None:
            return self._default_for_ports(ports, path)
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: spec.readiness must be an object")
        return self._from_raw(raw, ports, path)

    def _default_for_ports(self, ports: tuple[PortSpec, ...], path: Path) -> ReadinessSpec:
        timing = self._timing_from_raw({}, path)
        http_ports = [p for p in ports if p.expose == "http"]
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

    def _from_raw(
        self, raw: dict[str, Any], ports: tuple[PortSpec, ...], path: Path
    ) -> ReadinessSpec:
        rtype = str(raw.get("type", "http")).strip().lower() or "http"
        if rtype not in READINESS_TYPES:
            raise ValueError(
                f"{path}: readiness.type must be one of {sorted(READINESS_TYPES)}, "
                f"got {rtype!r}"
            )
        port_s = self._port_name(raw)
        probe_path = self._probe_path(raw)
        timing = self._timing_from_raw(raw, path)
        readiness = ReadinessSpec(type=rtype, port=port_s, path=probe_path, **timing)
        if rtype == "none":
            return readiness
        return self._bind_port(readiness, ports, path, probe_path=probe_path, timing=timing)

    def _bind_port(
        self,
        readiness: ReadinessSpec,
        ports: tuple[PortSpec, ...],
        path: Path,
        *,
        probe_path: str,
        timing: dict[str, Any],
    ) -> ReadinessSpec:
        try:
            resolved = readiness.resolve_port(ports)
        except KeyError as exc:
            raise ValueError(f"{path}: {exc}") from exc
        if resolved is None:
            raise ValueError(f"{path}: readiness requires a named port")
        if readiness.type == "http" and resolved.expose != "http":
            raise ValueError(
                f"{path}: readiness.type=http requires an expose=http port "
                f"(got {resolved.name!r} expose={resolved.expose!r})"
            )
        if readiness.port is None:
            return ReadinessSpec(
                type=readiness.type,
                port=resolved.name,
                path=probe_path,
                **timing,
            )
        return readiness

    def _timing_from_raw(self, raw: dict[str, Any], path: Path) -> dict[str, Any]:
        return self._resolve_timing(path, **self._raw_timing_fields(raw, path))

    def _raw_timing_fields(self, raw: dict[str, Any], path: Path) -> dict[str, Any]:
        f, i = self._optional_positive_float, self._optional_positive_int
        return dict(
            start=f(
                raw.get("startPeriodSeconds", raw.get("start_period_seconds")),
                path=path,
                field="startPeriodSeconds",
            ),
            interval=f(
                raw.get("intervalSeconds", raw.get("interval_seconds")),
                path=path,
                field="intervalSeconds",
            ),
            probe_timeout=f(
                raw.get("probeTimeoutSeconds", raw.get("probe_timeout_seconds")),
                path=path,
                field="probeTimeoutSeconds",
            ),
            retries=i(raw.get("retries"), path=path, field="retries"),
            timeout=f(
                raw.get("timeoutSeconds", raw.get("timeout_seconds")),
                path=path,
                field="timeoutSeconds",
            ),
        )

    def _resolve_timing(
        self,
        path: Path,
        *,
        start: Optional[float],
        interval: Optional[float],
        probe_timeout: Optional[float],
        retries: Optional[int],
        timeout: Optional[float],
    ) -> dict[str, Any]:
        start_period_seconds = start if start is not None else DEFAULT_START_PERIOD_SECONDS
        interval_seconds = interval if interval is not None else DEFAULT_INTERVAL_SECONDS
        probe_timeout_seconds = (
            probe_timeout if probe_timeout is not None else DEFAULT_PROBE_TIMEOUT_SECONDS
        )
        retries_n = retries if retries is not None else DEFAULT_RETRIES
        timeout_seconds = self._resolve_timeout(
            path,
            timeout=timeout,
            start_period_seconds=start_period_seconds,
            interval_seconds=interval_seconds,
            retries_n=retries_n,
        )
        return {
            "timeout_seconds": timeout_seconds,
            "start_period_seconds": start_period_seconds,
            "interval_seconds": interval_seconds,
            "probe_timeout_seconds": probe_timeout_seconds,
            "retries": retries_n,
        }

    @staticmethod
    def _resolve_timeout(
        path: Path,
        *,
        timeout: Optional[float],
        start_period_seconds: float,
        interval_seconds: float,
        retries_n: int,
    ) -> float:
        if timeout is None:
            return default_timeout_seconds(
                start_period_seconds=start_period_seconds,
                interval_seconds=interval_seconds,
                retries=retries_n,
            )
        if timeout <= start_period_seconds:
            raise ValueError(
                f"{path}: readiness.timeoutSeconds ({timeout:g}) must be "
                f"greater than startPeriodSeconds ({start_period_seconds:g})"
            )
        min_useful = start_period_seconds + interval_seconds
        if timeout < min_useful:
            raise ValueError(
                f"{path}: readiness.timeoutSeconds ({timeout:g}) must be "
                f"at least startPeriodSeconds + intervalSeconds "
                f"({min_useful:g}s)"
            )
        return timeout

    @staticmethod
    def _port_name(raw: dict[str, Any]) -> Optional[str]:
        port_name = raw.get("port")
        port_s = str(port_name).strip() if port_name is not None else None
        return None if port_s == "" else port_s

    @staticmethod
    def _probe_path(raw: dict[str, Any]) -> str:
        path_raw = raw.get("path", "/")
        probe_path = str(path_raw).strip() or "/"
        if not probe_path.startswith("/"):
            return f"/{probe_path}"
        return probe_path

    @staticmethod
    def _optional_positive_float(raw: Any, *, path: Path, field: str) -> Optional[float]:
        if raw is None:
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{path}: readiness.{field} must be a number") from exc
        if value <= 0:
            raise ValueError(f"{path}: readiness.{field} must be > 0")
        return value

    @staticmethod
    def _optional_positive_int(raw: Any, *, path: Path, field: str) -> Optional[int]:
        if raw is None:
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{path}: readiness.{field} must be an integer") from exc
        if value <= 0:
            raise ValueError(f"{path}: readiness.{field} must be > 0")
        return value


def parse_readiness(
    spec: dict[str, Any],
    ports: tuple[PortSpec, ...],
    path: Path,
) -> ReadinessSpec:
    return ReadinessParser().parse(spec, ports, path)
