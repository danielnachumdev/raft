"""Logs download as JSON (service, tail, lines) — not raw secrets dumps."""

from __future__ import annotations

import json
from typing import Any, Dict

from .format import Exporter, ExportSpec


class LogsJsonExporter(Exporter):
    """``.json`` encoder for a logs snapshot payload."""

    def __init__(self) -> None:
        super().__init__(
            ExportSpec(
                format_id="json",
                label="JSON",
                media_type="application/json",
                suffix="json",
            )
        )

    def encode(self, payload: Any) -> bytes:
        body = json.dumps(
            self._document(payload), indent=2, ensure_ascii=False
        )
        return (body + "\n").encode("utf-8")

    @staticmethod
    def _document(payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {"service": "", "tail": 0, "lines": []}
        text = payload.get("text") if isinstance(payload.get("text"), str) else ""
        service = payload.get("service")
        tail = payload.get("tail")
        return {
            "service": service if isinstance(service, str) else "",
            "tail": tail if isinstance(tail, int) else 0,
            "lines": text.splitlines(),
        }
