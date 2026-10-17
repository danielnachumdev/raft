"""Shared logs/metrics export encode path (serve downloads + CLI)."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.ops.logs import DEFAULT_LOG_TAIL, Logs
from raft.core.observe.read import MetricsRead

from .catalogs import ExportCatalogs
from .exporter import Exporter
from .registry import ExportRegistry
from .unknown_format import UnknownExportFormat

EXPORT_MAX_POINTS = 50_000
MAX_LOG_TAIL = 5000


class ExportService:
    """Catalog + encode attachments without FastAPI/Fire types."""

    def __init__(
        self,
        stack: Stack,
        *,
        logs: Optional[Logs] = None,
        logs_formats: Optional[ExportRegistry] = None,
        metrics_formats: Optional[ExportRegistry] = None,
        metrics: Optional[MetricsRead] = None,
    ) -> None:
        self._stack = stack
        self._logs = logs or Logs(stack)
        self._metrics = metrics or MetricsRead(stack.root)
        self._logs_formats = logs_formats or ExportCatalogs.logs()
        self._metrics_formats = metrics_formats or ExportCatalogs.metrics()

    def catalog(self) -> Dict[str, Any]:
        return {
            "logs": self._logs_formats.catalog(),
            "metrics": self._metrics_formats.catalog(),
        }

    def encode_logs(
        self,
        name: str,
        *,
        format_id: str = "txt",
        tail: int = DEFAULT_LOG_TAIL,
    ) -> Tuple[Exporter, bytes, str]:
        exporter = self._require(self._logs_formats, format_id)
        lines = self._clamp_tail(tail)
        payload = {
            "service": name,
            "tail": lines,
            "text": self._logs.snapshot(name, tail=lines),
        }
        return exporter, exporter.encode(payload), f"raft-logs-{name}"

    def encode_metrics(
        self,
        *,
        format_id: str = "csv",
        window: int = 3600,
        services: Optional[Sequence[str]] = None,
    ) -> Tuple[Exporter, bytes, str]:
        exporter = self._require(self._metrics_formats, format_id)
        payload = self._metrics.history(
            window_seconds=window,
            services=list(services) if services else None,
            max_points=EXPORT_MAX_POINTS,
        )
        return exporter, exporter.encode(payload), "raft-metrics"

    @staticmethod
    def split_services(raw: Optional[str]) -> Optional[List[str]]:
        if raw is None or not raw.strip():
            return None
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return parts or None

    @staticmethod
    def write_bytes(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    @staticmethod
    def _require(registry: ExportRegistry, format_id: str) -> Exporter:
        try:
            return registry.get(format_id)
        except UnknownExportFormat as exc:
            raise OperatorError(str(exc), has_fix=False) from exc

    @staticmethod
    def _clamp_tail(tail: int) -> int:
        if tail < 1:
            return 1
        if tail > MAX_LOG_TAIL:
            return MAX_LOG_TAIL
        return tail
