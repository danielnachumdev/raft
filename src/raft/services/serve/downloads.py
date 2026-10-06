"""Serve download endpoints over the export registry (catalog + attachments)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from fastapi.responses import Response

from raft.errors.cta import OperatorError

from ...models.stack import Stack
from ..export.attachment import ExportAttachment
from ..export.catalogs import ExportCatalogs
from ..export.registry import ExportRegistry, UnknownExportFormat
from ..ops.logs import DEFAULT_LOG_TAIL, Logs
from ..read.metrics import MetricsRead

_MAX_LOG_TAIL = 5000
_EXPORT_MAX_POINTS = 50_000


class ServeDownloads:
    """Catalog JSON + file downloads; formats come from ExportCatalogs."""

    def __init__(
        self,
        stack: Stack,
        logs: Optional[Logs] = None,
        logs_formats: Optional[ExportRegistry] = None,
        metrics_formats: Optional[ExportRegistry] = None,
        metrics: Optional[MetricsRead] = None,
    ) -> None:
        self._logs = logs or Logs(stack)
        self._metrics = metrics or MetricsRead(stack.root)
        self._logs_formats = logs_formats or ExportCatalogs.logs()
        self._metrics_formats = metrics_formats or ExportCatalogs.metrics()

    def api_export_catalog(self) -> Dict[str, Any]:
        return {
            "logs": self._logs_formats.catalog(),
            "metrics": self._metrics_formats.catalog(),
        }

    def api_logs_download(
        self,
        name: str,
        format: str = "txt",
        tail: int = DEFAULT_LOG_TAIL,
    ) -> Response:
        exporter = self._require(self._logs_formats, format)
        lines = self._clamp_tail(tail)
        payload = self._logs_payload(name, lines)
        return ExportAttachment.response(
            exporter, exporter.encode(payload), f"raft-logs-{name}"
        )

    def api_metrics_download(
        self,
        format: str = "csv",
        window: int = 3600,
        services: Optional[str] = None,
    ) -> Response:
        exporter = self._require(self._metrics_formats, format)
        payload = self._metrics.history(
            window_seconds=window,
            services=self._split_services(services),
            max_points=_EXPORT_MAX_POINTS,
        )
        return ExportAttachment.response(
            exporter, exporter.encode(payload), "raft-metrics"
        )

    def _logs_payload(self, name: str, tail: int) -> Dict[str, Any]:
        try:
            text = self._logs.snapshot(name, tail=tail)
        except OperatorError as exc:
            raise self._http_for_operator(exc) from exc
        return {"service": name, "tail": tail, "text": text}

    @staticmethod
    def _require(registry: ExportRegistry, format_id: str):
        try:
            return registry.get(format_id)
        except UnknownExportFormat as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @staticmethod
    def _clamp_tail(tail: int) -> int:
        if tail < 1:
            return 1
        if tail > _MAX_LOG_TAIL:
            return _MAX_LOG_TAIL
        return tail

    @staticmethod
    def _http_for_operator(exc: OperatorError) -> HTTPException:
        text = str(exc)
        code = 404 if text.startswith("unknown") else 400
        return HTTPException(status_code=code, detail=text)

    @staticmethod
    def _split_services(raw: Optional[str]) -> Optional[List[str]]:
        if raw is None or not raw.strip():
            return None
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return parts or None
