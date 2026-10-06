"""Logs download as UTF-8 plain text (container stdout/stderr)."""

from __future__ import annotations

from typing import Any

from .format import Exporter, ExportSpec


class LogsTxtExporter(Exporter):
    """``.txt`` encoder for a logs snapshot payload."""

    def __init__(self) -> None:
        super().__init__(
            ExportSpec(
                format_id="txt",
                label="Plain text",
                media_type="text/plain; charset=utf-8",
                suffix="txt",
            )
        )

    def encode(self, payload: Any) -> bytes:
        text = LogsTxtExporter._text(payload)
        if text and not text.endswith("\n"):
            text += "\n"
        return text.encode("utf-8")

    @staticmethod
    def _text(payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""
        text = payload.get("text")
        return text if isinstance(text, str) else ""
