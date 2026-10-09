"""Aggregate gate access-log lines into one HTTP metrics sample window."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


@dataclass
class _Bucket:
    durations_ms: List[float] = field(default_factory=list)
    status_class: Dict[str, int] = field(
        default_factory=lambda: {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "other": 0}
    )

    def add(self, duration_s: float, status: int) -> None:
        self.durations_ms.append(duration_s * 1000.0)
        key = self._class_key(status)
        self.status_class[key] = self.status_class.get(key, 0) + 1

    @staticmethod
    def _class_key(status: int) -> str:
        if 200 <= status < 300:
            return "2xx"
        if 300 <= status < 400:
            return "3xx"
        if 400 <= status < 500:
            return "4xx"
        if 500 <= status < 600:
            return "5xx"
        return "other"


class HttpMetricsAggregator:
    """Build edge + per-host / per-app samples for one scrape interval."""

    def aggregate(
        self,
        lines: Sequence[str],
        *,
        interval_seconds: float,
        in_flight: Optional[int],
        active_connections: Optional[int],
        host_to_service: Mapping[str, str],
    ) -> Dict[str, object]:
        edge, by_host = self._fill_buckets(lines)
        interval = max(float(interval_seconds), 1e-6)
        return self._sample(
            edge,
            by_host,
            interval=interval,
            in_flight=in_flight,
            active_connections=active_connections,
            host_to_service=host_to_service,
        )

    def _fill_buckets(
        self, lines: Sequence[str]
    ) -> Tuple[_Bucket, Dict[str, _Bucket]]:
        edge = _Bucket()
        by_host: Dict[str, _Bucket] = {}
        for line in lines:
            parsed = self.parse_line(line)
            if parsed is None:
                continue
            duration_s, status, host = parsed
            edge.add(duration_s, status)
            by_host.setdefault(host, _Bucket()).add(duration_s, status)
        return edge, by_host

    def _sample(
        self,
        edge: _Bucket,
        by_host: Dict[str, _Bucket],
        *,
        interval: float,
        in_flight: Optional[int],
        active_connections: Optional[int],
        host_to_service: Mapping[str, str],
    ) -> Dict[str, object]:
        return {
            "interval_seconds": round(interval, 3),
            "scope": "edge",
            "in_flight": in_flight,
            "active_connections": active_connections,
            "in_flight_proxy": "nginx_stub_status_writing",
            **self._window(edge, interval),
            "by_host": {
                host: self._window(bucket, interval) for host, bucket in by_host.items()
            },
            "by_service": self._by_service(by_host, host_to_service, interval),
        }

    def _by_service(
        self,
        by_host: Mapping[str, _Bucket],
        host_to_service: Mapping[str, str],
        interval: float,
    ) -> Dict[str, Dict[str, object]]:
        merged: Dict[str, _Bucket] = {}
        for host, bucket in by_host.items():
            service = host_to_service.get(host.lower())
            if not service:
                continue
            target = merged.setdefault(service, _Bucket())
            target.durations_ms.extend(bucket.durations_ms)
            for key, count in bucket.status_class.items():
                target.status_class[key] = target.status_class.get(key, 0) + count
        return {sid: self._window(bucket, interval) for sid, bucket in merged.items()}

    def _window(self, bucket: _Bucket, interval: float) -> Dict[str, object]:
        count = len(bucket.durations_ms)
        return {
            "requests": count,
            "rps": round(count / interval, 4),
            "duration_ms": self.percentiles(bucket.durations_ms),
            "status_class": dict(bucket.status_class),
        }

    @staticmethod
    def parse_line(raw: str) -> Optional[Tuple[float, int, str]]:
        parts = raw.strip().split()
        if len(parts) < 3:
            return None
        try:
            duration_s = float(parts[0])
            status = int(parts[1])
        except ValueError:
            return None
        host = parts[2].lower()
        if not host or host == "-":
            return None
        return duration_s, status, host

    @staticmethod
    def percentiles(values_ms: Sequence[float]) -> Dict[str, Optional[float]]:
        if not values_ms:
            return {"avg": None, "p50": None, "p95": None, "p99": None}
        ordered = sorted(values_ms)
        avg = sum(ordered) / float(len(ordered))
        return {
            "avg": round(avg, 3),
            "p50": round(HttpMetricsAggregator._rank(ordered, 0.50), 3),
            "p95": round(HttpMetricsAggregator._rank(ordered, 0.95), 3),
            "p99": round(HttpMetricsAggregator._rank(ordered, 0.99), 3),
        }

    @staticmethod
    def _rank(ordered: Sequence[float], q: float) -> float:
        if len(ordered) == 1:
            return float(ordered[0])
        # Nearest-rank with 1-based index (inclusive of last sample).
        idx = max(1, min(len(ordered), int(round(q * len(ordered))))) - 1
        return float(ordered[idx])
