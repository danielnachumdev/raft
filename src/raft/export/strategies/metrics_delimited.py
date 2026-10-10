"""Metrics series as a delimited table (CSV shipped; TSV is the same class)."""

from __future__ import annotations

import csv
import io
from typing import Any, List

from ..format import Exporter, ExportSpec

_POINT_KEYS = (
    "cpu_percent",
    "memory_used_percent",
    "memory_used_bytes",
    "memory_limit_bytes",
    "uptime_seconds",
    "pids",
    "network_rx_bytes",
    "network_tx_bytes",
    "block_read_bytes",
    "block_write_bytes",
)


class DelimitedMetricsExporter(Exporter):
    """Flatten ``MetricsRead`` series into rows. Register ``tsv()`` for TSV."""

    COLUMNS = ("t", "series_id", "label", "kind", "role", "group") + _POINT_KEYS

    def __init__(self, spec: ExportSpec, delimiter: str) -> None:
        super().__init__(spec)
        self._delimiter = delimiter

    @classmethod
    def csv(cls) -> "DelimitedMetricsExporter":
        return cls(
            ExportSpec(
                format_id="csv",
                label="CSV",
                media_type="text/csv; charset=utf-8",
                suffix="csv",
            ),
            ",",
        )

    @classmethod
    def tsv(cls) -> "DelimitedMetricsExporter":
        """Extension point — not registered in the shipped catalog."""
        return cls(
            ExportSpec(
                format_id="tsv",
                label="TSV",
                media_type="text/tab-separated-values; charset=utf-8",
                suffix="tsv",
            ),
            "\t",
        )

    def encode(self, payload: Any) -> bytes:
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=self._delimiter, lineterminator="\n")
        writer.writerow(self.COLUMNS)
        writer.writerows(self._rows(payload))
        return buf.getvalue().encode("utf-8")

    def _rows(self, payload: Any) -> List[List[str]]:
        series_list = payload.get("series") if isinstance(payload, dict) else None
        if not isinstance(series_list, list):
            return []
        rows: List[List[str]] = []
        for series in series_list:
            if isinstance(series, dict):
                rows.extend(self._series_rows(series))
        return rows

    def _series_rows(self, series: dict) -> List[List[str]]:
        points = series.get("points")
        if not isinstance(points, list):
            return []
        meta = self._meta(series)
        return [
            self._row(meta, point) for point in points if isinstance(point, dict)
        ]

    @staticmethod
    def _row(meta: List[str], point: dict) -> List[str]:
        cells = [DelimitedMetricsExporter._cell(point.get("t"))]
        cells.extend(meta)
        cells.extend(
            DelimitedMetricsExporter._cell(point.get(key)) for key in _POINT_KEYS
        )
        return cells

    @staticmethod
    def _meta(series: dict) -> List[str]:
        return [
            DelimitedMetricsExporter._cell(series.get("id")),
            DelimitedMetricsExporter._cell(series.get("label")),
            DelimitedMetricsExporter._cell(series.get("kind")),
            DelimitedMetricsExporter._cell(series.get("role")),
            DelimitedMetricsExporter._cell(series.get("group")),
        ]

    @staticmethod
    def _cell(value: Any) -> str:
        if value is None:
            return ""
        return str(value)
