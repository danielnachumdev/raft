"""Build chart series points from parsed metrics samples."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from raft.models import display_service_label

HOST_SERIES_ID = "host"


class MetricsSeriesBuilder:
    """Turn raw JSONL samples into named host/container series."""

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
            self._add_host(out, sample, ts=ts, wanted=wanted)
            self._add_containers(out, sample, ts=ts, wanted=wanted)
        return out

    def available(self, samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: Dict[str, Dict[str, Any]] = {}
        for sample in samples:
            self._note_host(seen, sample)
            self._note_containers(seen, sample)
        return list(seen.values())

    def _add_host(
        self,
        out: Dict[str, Dict[str, Any]],
        sample: Dict[str, Any],
        *,
        ts: str,
        wanted: Optional[Set[str]],
    ) -> None:
        if wanted is not None and HOST_SERIES_ID not in wanted:
            return
        host = sample.get("host")
        if not isinstance(host, dict):
            return
        series = out.setdefault(HOST_SERIES_ID, self._host_meta())
        series["points"].append(self._host_point(host, ts=ts))

    def _add_containers(
        self,
        out: Dict[str, Dict[str, Any]],
        sample: Dict[str, Any],
        *,
        ts: str,
        wanted: Optional[Set[str]],
    ) -> None:
        rows = sample.get("containers")
        if not isinstance(rows, list):
            return
        for row in rows:
            self._add_one_container(out, row, ts=ts, wanted=wanted)

    def _add_one_container(
        self,
        out: Dict[str, Dict[str, Any]],
        row: Any,
        *,
        ts: str,
        wanted: Optional[Set[str]],
    ) -> None:
        if not isinstance(row, dict):
            return
        service = row.get("service")
        if not isinstance(service, str) or not service:
            return
        if wanted is not None and service not in wanted:
            return
        series = out.setdefault(service, self._container_meta(row, service))
        series["points"].append(self._container_point(row, ts=ts))

    def _note_host(self, seen: Dict[str, Dict[str, Any]], sample: Dict[str, Any]) -> None:
        if isinstance(sample.get("host"), dict):
            seen.setdefault(HOST_SERIES_ID, self._host_meta_public())

    def _note_containers(
        self, seen: Dict[str, Dict[str, Any]], sample: Dict[str, Any]
    ) -> None:
        rows = sample.get("containers")
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, dict):
                continue
            service = row.get("service")
            if isinstance(service, str) and service and service not in seen:
                meta = self._container_meta(row, service)
                seen[service] = {
                    "id": meta["id"],
                    "label": meta["label"],
                    "kind": meta["kind"],
                    "role": meta["role"],
                    "group": meta.get("group"),
                }

    @staticmethod
    def _host_meta() -> Dict[str, Any]:
        return {**MetricsSeriesBuilder._host_meta_public(), "points": []}

    @staticmethod
    def _host_meta_public() -> Dict[str, Any]:
        return {
            "id": HOST_SERIES_ID,
            "label": "Host",
            "kind": "host",
            "role": "host",
            "group": None,
        }

    @staticmethod
    def _container_meta(row: Dict[str, Any], service: str) -> Dict[str, Any]:
        group = row.get("group") if isinstance(row.get("group"), str) else None
        role = row.get("role") if isinstance(row.get("role"), str) else "app"
        return {
            "id": service,
            "label": display_service_label(service, group),
            "kind": "container",
            "role": role,
            "group": group,
            "points": [],
        }

    @staticmethod
    def _host_point(host: Dict[str, Any], *, ts: str) -> Dict[str, Any]:
        mem = host.get("memory") if isinstance(host.get("memory"), dict) else {}
        return {
            "t": ts,
            "cpu_percent": MetricsSeriesBuilder._host_cpu_percent(host),
            "memory_used_percent": MetricsSeriesBuilder._as_float(mem.get("used_percent")),
            "memory_used_bytes": MetricsSeriesBuilder._as_float(mem.get("used_bytes")),
        }

    @staticmethod
    def _host_cpu_percent(host: Dict[str, Any]) -> Optional[float]:
        # Snapshot has loadavg, not docker-style CPU %; normalize by CPU count.
        load = host.get("loadavg")
        if not isinstance(load, list) or not load:
            return None
        try:
            load1 = float(load[0])
            cpus = host.get("cpus")
            if cpus:
                return round((load1 / float(cpus)) * 100.0, 2)
            return load1
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    @staticmethod
    def _container_point(row: Dict[str, Any], *, ts: str) -> Dict[str, Any]:
        """Map one Status container row onto chartable Runtime series fields."""
        mem = MetricsSeriesBuilder._as_dict(row.get("memory"))
        net = MetricsSeriesBuilder._as_dict(row.get("network"))
        block = MetricsSeriesBuilder._as_dict(row.get("block_io"))
        point: Dict[str, Any] = {"t": ts}
        point.update(MetricsSeriesBuilder._container_core(row, mem))
        point.update(MetricsSeriesBuilder._container_io(net, block))
        return point

    @staticmethod
    def _container_core(
        row: Dict[str, Any], mem: Dict[str, Any]
    ) -> Dict[str, Optional[float]]:
        return {
            "cpu_percent": MetricsSeriesBuilder._as_float(row.get("cpu_percent")),
            "memory_used_percent": MetricsSeriesBuilder._as_float(mem.get("used_percent")),
            "memory_used_bytes": MetricsSeriesBuilder._as_float(mem.get("used_bytes")),
            "memory_limit_bytes": MetricsSeriesBuilder._as_float(mem.get("limit_bytes")),
            "uptime_seconds": MetricsSeriesBuilder._as_float(row.get("uptime_seconds")),
            "pids": MetricsSeriesBuilder._as_float(row.get("pids")),
        }

    @staticmethod
    def _container_io(
        net: Dict[str, Any], block: Dict[str, Any]
    ) -> Dict[str, Optional[float]]:
        return {
            "network_rx_bytes": MetricsSeriesBuilder._as_float(net.get("rx_bytes")),
            "network_tx_bytes": MetricsSeriesBuilder._as_float(net.get("tx_bytes")),
            "block_read_bytes": MetricsSeriesBuilder._as_float(block.get("read_bytes")),
            "block_write_bytes": MetricsSeriesBuilder._as_float(
                block.get("write_bytes")
            ),
        }

    @staticmethod
    def _as_dict(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        if value is None or isinstance(value, bool):
            return None
        try:
            out = float(value)
        except (TypeError, ValueError):
            return None
        return out if out == out else None  # NaN check

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
