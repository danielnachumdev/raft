"""Serve download endpoints over the shared ``ExportService``."""

from typing import Any, Dict, Optional

from fastapi import HTTPException
from fastapi.responses import Response

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.export.attachment import ExportAttachment
from raft.core.observe.export.service import ExportService
from raft.core.observe.ops.logs import DEFAULT_LOG_TAIL, Logs
from raft.core.observe.read import MetricsRead


class ServeDownloads:
    """Thin FastAPI adapter over ``ExportService``."""

    def __init__(
        self,
        stack: Stack,
        logs: Optional[Logs] = None,
        metrics: Optional[MetricsRead] = None,
        service: Optional[ExportService] = None,
    ) -> None:
        self._service = service or ExportService(stack, logs=logs, metrics=metrics)

    def api_export_catalog(self) -> Dict[str, Any]:
        return self._service.catalog()

    def api_logs_download(
        self,
        name: str,
        format: str = "txt",
        tail: int = DEFAULT_LOG_TAIL,
    ) -> Response:
        try:
            exporter, body, stem = self._service.encode_logs(
                name, format_id=format, tail=tail
            )
        except OperatorError as exc:
            raise self._http_for_operator(exc) from exc
        return ExportAttachment.response(exporter, body, stem)

    def api_metrics_download(
        self,
        format: str = "csv",
        window: int = 3600,
        services: Optional[str] = None,
    ) -> Response:
        try:
            exporter, body, stem = self._service.encode_metrics(
                format_id=format,
                window=window,
                services=ExportService.split_services(services),
            )
        except OperatorError as exc:
            raise self._http_for_operator(exc) from exc
        return ExportAttachment.response(exporter, body, stem)

    @staticmethod
    def _http_for_operator(exc: OperatorError) -> HTTPException:
        text = str(exc)
        if text.startswith("unknown export format"):
            code = 400
        elif text.startswith("unknown"):
            code = 404
        else:
            code = 400
        return HTTPException(status_code=code, detail=text)
