"""Metrics JSONL and gate access-log paths under the data home."""

from pathlib import Path

METRICS_DIR = Path("state") / "metrics"
METRICS_FILENAME = "resources.jsonl"
HTTP_METRICS_FILENAME = "http.jsonl"
GATE_HTTP_LOG_DIR = METRICS_DIR / "gate-http"
ACCESS_LOG_NAME = "access.log"


class MetricsPaths:
    """Resolved metrics paths for a raft data home."""

    def __init__(self, home: Path) -> None:
        self._home = home

    def dir(self) -> Path:
        return self._home / METRICS_DIR

    def resources(self) -> Path:
        return self.dir() / METRICS_FILENAME

    def http(self) -> Path:
        return self.dir() / HTTP_METRICS_FILENAME

    def gate_access_log(self) -> Path:
        return self._home / GATE_HTTP_LOG_DIR / ACCESS_LOG_NAME
