"""Scrape gate access.log + stub_status for HTTP request metrics."""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Tuple

from raft.models.app import App
from raft.models.stack import Stack

from .http_metrics_agg import HttpMetricsAggregator
from .metrics import METRICS_DIR

logger = logging.getLogger(__name__)

GATE_HTTP_LOG_DIR = METRICS_DIR / "gate-http"
ACCESS_LOG_NAME = "access.log"
OFFSET_NAME = "access.offset"
DEFAULT_STUB_STATUS_URL = "http://raft-gate:8081/nginx_status"

FetchText = Callable[[str], str]
HostMapFn = Callable[[], Mapping[str, str]]


class GateHttpScraper:
    """Read new access-log bytes + stub_status; return one aggregate sample."""

    def __init__(
        self,
        home: Path,
        *,
        interval_seconds: float,
        stub_status_url: str = DEFAULT_STUB_STATUS_URL,
        fetch_text: Optional[FetchText] = None,
        host_map_fn: Optional[HostMapFn] = None,
        aggregator: Optional[HttpMetricsAggregator] = None,
    ) -> None:
        self.home = home
        self.interval_seconds = float(interval_seconds)
        self.stub_status_url = stub_status_url
        self._fetch_text = fetch_text or self._http_get
        self._host_map_fn = host_map_fn or self._default_host_map
        self._agg = aggregator or HttpMetricsAggregator()

    @property
    def log_path(self) -> Path:
        return self.home / GATE_HTTP_LOG_DIR / ACCESS_LOG_NAME

    @property
    def offset_path(self) -> Path:
        return self.home / GATE_HTTP_LOG_DIR / OFFSET_NAME

    def sample(self) -> Dict[str, object]:
        lines = self._read_new_lines()
        writing, active = self._stub_status()
        return self._agg.aggregate(
            lines,
            interval_seconds=self.interval_seconds,
            in_flight=writing,
            active_connections=active,
            host_to_service=dict(self._host_map_fn()),
        )

    def _read_new_lines(self) -> List[str]:
        path = self.log_path
        if not path.is_file():
            return []
        offset = self._load_offset()
        data, new_offset = self._read_from_offset(path, offset)
        self._store_offset(new_offset)
        if not data:
            return []
        text = data.decode("utf-8", errors="replace")
        return [line for line in text.splitlines() if line.strip()]

    def _read_from_offset(self, path: Path, offset: int) -> Tuple[bytes, int]:
        size = path.stat().st_size
        if offset > size:
            offset = 0
        with path.open("rb") as handle:
            handle.seek(offset)
            data = handle.read()
            return data, handle.tell()

    def _load_offset(self) -> int:
        try:
            raw = self.offset_path.read_text(encoding="utf-8").strip()
            return max(0, int(raw))
        except (OSError, ValueError):
            return 0

    def _store_offset(self, offset: int) -> None:
        self.offset_path.parent.mkdir(parents=True, exist_ok=True)
        self.offset_path.write_text(f"{offset}\n", encoding="utf-8")

    def _stub_status(self) -> Tuple[Optional[int], Optional[int]]:
        try:
            text = self._fetch_text(self.stub_status_url)
        except (OSError, urllib.error.URLError) as exc:
            logger.debug("gate stub_status scrape failed: %s", exc)
            return None, None
        return self.parse_stub_status(text)

    def _default_host_map(self) -> Mapping[str, str]:
        stack = Stack.load_apps(self.home)
        return self.host_map_for_apps(stack.apps, stack)

    @staticmethod
    def host_map_for_apps(apps: Tuple[App, ...], stack: Stack) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for app in apps:
            if app.public_host:
                out[app.public_host.lower()] = app.compose_id
            for host in GateHttpScraper._extra_hosts(stack, app):
                out[host.lower()] = app.compose_id
        return out

    @staticmethod
    def _extra_hosts(stack: Stack, app: App) -> Tuple[str, ...]:
        try:
            return tuple(stack.spec_for(app).extra_hosts)
        except Exception:  # noqa: BLE001 — skip bad registry rows for scrape
            return ()

    @staticmethod
    def parse_stub_status(text: str) -> Tuple[Optional[int], Optional[int]]:
        active: Optional[int] = None
        writing: Optional[int] = None
        for line in text.splitlines():
            lower = line.lower().strip()
            if lower.startswith("active connections:"):
                active = GateHttpScraper._trailing_int(line)
            elif lower.startswith("reading:"):
                writing = GateHttpScraper._field_int(line, "writing:")
        return writing, active

    @staticmethod
    def _trailing_int(line: str) -> Optional[int]:
        parts = line.split(":")
        if len(parts) < 2:
            return None
        try:
            return int(parts[-1].strip())
        except ValueError:
            return None

    @staticmethod
    def _field_int(line: str, label: str) -> Optional[int]:
        lower = line.lower()
        idx = lower.find(label)
        if idx < 0:
            return None
        rest = line[idx + len(label) :].strip().split()
        if not rest:
            return None
        try:
            return int(rest[0])
        except ValueError:
            return None

    @staticmethod
    def _http_get(url: str) -> str:
        with urllib.request.urlopen(url, timeout=2.0) as resp:  # noqa: S310
            return resp.read().decode("utf-8", errors="replace")
