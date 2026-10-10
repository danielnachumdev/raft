"""Build chart series from ``http.jsonl`` samples."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

EDGE_SERIES_ID = "edge"


class HttpMetricsSeriesBuilder:
    """Turn HTTP JSONL samples into edge + per-service series."""

    def build(
        self,
        samples: List[Dict[str, Any]],
        *,
        wanted: Optional[Set[str]],
    ) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for sample in samples:
            ts = sample.get("ts")
            if not isinstance(ts, str):
                continue
            self._add_edge(out, sample, ts=ts, wanted=wanted)
            self._add_services(out, sample, ts=ts, wanted=wanted)
        return out

    def available(self, samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: Dict[str, Dict[str, Any]] = {}
        for sample in samples:
            seen.setdefault(EDGE_SERIES_ID, self._edge_meta_public())
            services = sample.get("by_service")
            if not isinstance(services, dict):
                continue
            for service in services:
                if isinstance(service, str) and service and service not in seen:
                    seen[service] = self._service_meta_public(service)
        return list(seen.values())

    def _add_edge(
        self,
        out: Dict[str, Dict[str, Any]],
        sample: Dict[str, Any],
        *,
        ts: str,
        wanted: Optional[Set[str]],
    ) -> None:
        if wanted is not None and EDGE_SERIES_ID not in wanted:
            return
        series = out.setdefault(EDGE_SERIES_ID, self._edge_meta())
        series["points"].append(self._point(sample, ts=ts, include_concurrency=True))

    def _add_services(
        self,
        out: Dict[str, Dict[str, Any]],
        sample: Dict[str, Any],
        *,
        ts: str,
        wanted: Optional[Set[str]],
    ) -> None:
        services = sample.get("by_service")
        if not isinstance(services, dict):
            return
        for service, payload in services.items():
            if not isinstance(service, str) or not service:
                continue
            if wanted is not None and service not in wanted:
                continue
            if not isinstance(payload, dict):
                continue
            series = out.setdefault(service, self._service_meta(service))
            series["points"].append(
                self._point(payload, ts=ts, include_concurrency=False)
            )

    @staticmethod
    def _edge_meta() -> Dict[str, Any]:
        return {**HttpMetricsSeriesBuilder._edge_meta_public(), "points": []}

    @staticmethod
    def _edge_meta_public() -> Dict[str, Any]:
        return {
            "id": EDGE_SERIES_ID,
            "label": "HTTP edge",
            "kind": "http",
            "role": "edge",
            "group": "raft",
        }

    @staticmethod
    def _service_meta(service: str) -> Dict[str, Any]:
        return {**HttpMetricsSeriesBuilder._service_meta_public(service), "points": []}

    @staticmethod
    def _service_meta_public(service: str) -> Dict[str, Any]:
        return {
            "id": service,
            "label": service,
            "kind": "http",
            "role": "app",
            "group": None,
        }

    @staticmethod
    def _point(
        row: Dict[str, Any], *, ts: str, include_concurrency: bool
    ) -> Dict[str, Any]:
        point: Dict[str, Any] = {"t": ts}
        point.update(HttpMetricsSeriesBuilder._rate_fields(row))
        point.update(HttpMetricsSeriesBuilder._duration_fields(row))
        point.update(HttpMetricsSeriesBuilder._status_fields(row))
        if include_concurrency:
            point.update(HttpMetricsSeriesBuilder._concurrency_fields(row))
        return point

    @staticmethod
    def _rate_fields(row: Dict[str, Any]) -> Dict[str, Optional[float]]:
        return {
            "rps": HttpMetricsSeriesBuilder._as_float(row.get("rps")),
            "requests": HttpMetricsSeriesBuilder._as_float(row.get("requests")),
        }

    @staticmethod
    def _duration_fields(row: Dict[str, Any]) -> Dict[str, Optional[float]]:
        duration = row.get("duration_ms") if isinstance(row.get("duration_ms"), dict) else {}
        return {
            "duration_avg_ms": HttpMetricsSeriesBuilder._as_float(duration.get("avg")),
            "duration_p50_ms": HttpMetricsSeriesBuilder._as_float(duration.get("p50")),
            "duration_p95_ms": HttpMetricsSeriesBuilder._as_float(duration.get("p95")),
            "duration_p99_ms": HttpMetricsSeriesBuilder._as_float(duration.get("p99")),
        }

    @staticmethod
    def _status_fields(row: Dict[str, Any]) -> Dict[str, Optional[float]]:
        status = row.get("status_class") if isinstance(row.get("status_class"), dict) else {}
        return {
            "status_2xx": HttpMetricsSeriesBuilder._as_float(status.get("2xx")),
            "status_3xx": HttpMetricsSeriesBuilder._as_float(status.get("3xx")),
            "status_4xx": HttpMetricsSeriesBuilder._as_float(status.get("4xx")),
            "status_5xx": HttpMetricsSeriesBuilder._as_float(status.get("5xx")),
        }

    @staticmethod
    def _concurrency_fields(row: Dict[str, Any]) -> Dict[str, Optional[float]]:
        return {
            "in_flight": HttpMetricsSeriesBuilder._as_float(row.get("in_flight")),
            "active_connections": HttpMetricsSeriesBuilder._as_float(
                row.get("active_connections")
            ),
        }

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        if value is None or isinstance(value, bool):
            return None
        try:
            out = float(value)
        except (TypeError, ValueError):
            return None
        return out if out == out else None

    @staticmethod
    def downsample(series: Dict[str, Any], *, max_points: int) -> Dict[str, Any]:
        points = series["points"]
        if max_points < 1 or len(points) <= max_points:
            return series
        step = len(points) / float(max_points)
        picked = [points[min(len(points) - 1, int(i * step))] for i in range(max_points)]
        out = dict(series)
        out["points"] = picked
        return out
