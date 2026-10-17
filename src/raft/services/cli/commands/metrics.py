"""Fire component: ``raft metrics …`` (history query + exports)."""

import json as json_lib
import sys
from pathlib import Path
from typing import Optional, Sequence

from raft.core.core.models.stack import Stack
from raft.core.core.ui import OperatorSay
from raft.core.observe.export.service import ExportService
from raft.core.observe.read import HttpMetricsRead, MetricsRead
from raft.core.observe.read.metrics.window import DEFAULT_WINDOW_SECONDS


class MetricsCLI:
    """Historical metrics query and catalog exports (same cores as serve)."""

    def __init__(
        self,
        stack: Stack,
        *,
        resources: Optional[MetricsRead] = None,
        http: Optional[HttpMetricsRead] = None,
        exports: Optional[ExportService] = None,
    ) -> None:
        self._stack = stack
        self._resources = resources or MetricsRead(stack.root)
        self._http = http or HttpMetricsRead(stack.root)
        self._exports = exports or ExportService(stack)

    def history(
        self,
        window: int = DEFAULT_WINDOW_SECONDS,
        start: Optional[str] = None,
        end: Optional[str] = None,
        service: Optional[str] = None,
        http: bool = False,
        json: bool = True,
    ) -> None:
        """Query resource or HTTP edge history (fields match ``/api/metrics*``).

        Example::

            raft metrics history --window=3600 --service=demo-api
            raft metrics history --http --window=900 --json
        """
        payload = self._history_payload(
            window=window, start=start, end=end, service=service, http=http
        )
        if json:
            OperatorSay.say(json_lib.dumps(payload, indent=2, sort_keys=False))
            return
        self._print_history_summary(payload, http=http)

    def _history_payload(
        self,
        *,
        window: int,
        start: Optional[str],
        end: Optional[str],
        service: Optional[str],
        http: bool,
    ):
        services = [service] if service else None
        reader = self._http if http else self._resources
        return reader.history(
            window_seconds=window,
            start=start,
            end=end,
            services=services,
        )

    @staticmethod
    def _print_history_summary(payload, *, http: bool) -> None:
        kind = "http" if http else "resources"
        series = payload.get("series") or []
        OperatorSay.say(
            f"{kind}: window={payload.get('window_seconds')}s "
            f"from={payload.get('from')} to={payload.get('to')} "
            f"series={len(series)}"
        )

    def catalog(self, json: bool = False) -> None:
        """List export formats for logs and metrics (serve ``/api/exports``)."""
        payload = self._exports.catalog()
        if json:
            OperatorSay.say(json_lib.dumps(payload, indent=2, sort_keys=False))
            return
        self._print_catalog(payload.get("logs") or [], label="logs")
        self._print_catalog(payload.get("metrics") or [], label="metrics")

    def export_metrics(
        self,
        format: str = "csv",
        window: int = DEFAULT_WINDOW_SECONDS,
        service: Optional[str] = None,
        file: Optional[str] = None,
    ) -> None:
        """Export metrics history (default CSV) to stdout or ``--file``.

        Example::

            raft metrics export_metrics --service=demo-api --file=out.csv
        """
        services: Optional[Sequence[str]] = [service] if service else None
        _exporter, body, _stem = self._exports.encode_metrics(
            format_id=format, window=window, services=services
        )
        self._emit(body, file=file)

    def export_logs(
        self,
        name: str,
        format: str = "txt",
        tail: int = 100,
        file: Optional[str] = None,
    ) -> None:
        """Export recent service logs (txt/json) to stdout or ``--file``.

        Example::

            raft metrics export_logs demo-api --format=txt --file=demo-api.log
        """
        _exporter, body, _stem = self._exports.encode_logs(
            name, format_id=format, tail=tail
        )
        self._emit(body, file=file)

    @staticmethod
    def _print_catalog(rows, *, label: str) -> None:
        if not rows:
            OperatorSay.say(f"{label}: (none)")
            return
        OperatorSay.say(f"{label}:")
        for row in rows:
            OperatorSay.say(
                f"  {row.get('id')}  {row.get('label') or row.get('id')}"
            )

    def _emit(self, body: bytes, *, file: Optional[str]) -> None:
        if file:
            path = Path(file).expanduser()
            ExportService.write_bytes(path, body)
            OperatorSay.say(f"Wrote {path} ({len(body)} bytes).")
            return
        sys.stdout.buffer.write(body)
        if not body.endswith(b"\n"):
            sys.stdout.buffer.write(b"\n")
