"""HTTP attachment wrapping for encoded export bytes."""

from __future__ import annotations

import re

from fastapi.responses import Response

from .format import Exporter

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


class ExportAttachment:
    """Build a download Response from an exporter and file stem."""

    @staticmethod
    def response(exporter: Exporter, body: bytes, stem: str) -> Response:
        name = ExportAttachment.filename(stem, exporter.spec.suffix)
        return Response(
            content=body,
            media_type=exporter.spec.media_type,
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @staticmethod
    def filename(stem: str, suffix: str) -> str:
        safe = _UNSAFE.sub("-", stem).strip("-._") or "raft-export"
        return f"{safe}.{suffix}"
