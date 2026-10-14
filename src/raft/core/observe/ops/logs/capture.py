"""Ship Docker container logs into a :class:`ServiceLogsStore` (cursor-aware)."""

import logging
import re
from typing import Optional, Protocol

from .meta import ServiceLogsMeta
from .store import ServiceLogsStore

logger = logging.getLogger(__name__)

# docker --timestamps: 2026-10-14T12:00:00.123456789Z line…
_TS_PREFIX = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z) (?P<body>.*)$"
)


class ContainerLogSource(Protocol):
    """Minimal Docker log fetch used by capture (testable without full stack)."""

    def fetch(self, container: str, *, since: str) -> str:
        """Return ``docker logs --timestamps`` text for ``container``."""


class ServiceLogsCapture:
    """Append new Docker log lines for one logical service key."""

    def __init__(self, store: ServiceLogsStore, source: ContainerLogSource) -> None:
        self._store = store
        self._source = source

    def ship(self, key: str, container_id: str) -> int:
        """Drain new lines for ``container_id`` into ``key``; return line count."""
        if not key or not container_id:
            return 0
        meta = self._store.load_meta(key)
        meta = self._on_container_change(key, meta, container_id)
        raw = self._fetch(container_id, meta.cursor)
        lines, last_ts = self._parse_new_lines(raw, meta.cursor)
        if lines:
            self._store.append_lines(key, lines)
        if last_ts:
            meta.cursor = last_ts
        meta.container_id = container_id
        self._store.save_meta(key, meta)
        return len(lines)

    def _on_container_change(
        self, key: str, meta: ServiceLogsMeta, container_id: str
    ) -> ServiceLogsMeta:
        if meta.container_id and meta.container_id != container_id:
            self._store.note_generation(key, container_id)
            meta.generation = int(meta.generation) + 1
            meta.cursor = ""
        return meta

    def _fetch(self, container_id: str, cursor: str) -> str:
        try:
            return self._source.fetch(container_id, since=cursor) or ""
        except Exception as exc:  # noqa: BLE001 — best-effort shipper/drain
            logger.debug(
                "service-logs fetch failed container=%s err=%s",
                container_id[:12],
                exc,
            )
            return ""

    @staticmethod
    def _parse_new_lines(raw: str, cursor: str) -> tuple[list[str], str]:
        lines: list[str] = []
        last_ts = cursor
        for line in raw.splitlines():
            text = line.rstrip("\r")
            if not text.strip():
                continue
            match = _TS_PREFIX.match(text)
            if match is None:
                if cursor:
                    continue
                lines.append(text)
                continue
            ts = match.group("ts")
            body = match.group("body")
            if cursor and ts <= cursor:
                continue
            lines.append(body)
            last_ts = ts
        return lines, last_ts
