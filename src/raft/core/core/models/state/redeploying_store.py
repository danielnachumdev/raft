"""Durable live-cutover marker under ``services/<name>/deploy/redeploying``."""

from pathlib import Path

from raft.core.core.config.paths.service_paths import ServicePaths

# Gate nginx inspects this path (services bind mount) to choose maintenance.html.
REDEPLOYING_FILENAME = "redeploying"
CONTAINER_MARKER_TMPL = "/etc/nginx/services/{name}/deploy/" + REDEPLOYING_FILENAME


class RedeployingStore:
    """Presence means a live apply/redeploy cutover is in flight for the App."""

    def __init__(self, home: Path) -> None:
        self.home = home

    def _path(self, name: str) -> Path:
        return ServicePaths(self.home, name).deploy() / REDEPLOYING_FILENAME

    def is_redeploying(self, name: str) -> bool:
        return self._path(name).is_file()

    def mark(self, name: str) -> None:
        path = self._path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    def clear(self, name: str) -> None:
        path = self._path(name)
        if path.is_file():
            path.unlink()

    @staticmethod
    def container_marker(name: str) -> str:
        return CONTAINER_MARKER_TMPL.format(name=name)
