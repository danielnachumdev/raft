"""Durable operator Down marker under ``services/<name>/manual-stop``."""

from pathlib import Path

from raft.core.core.config.paths.service_paths import ServicePaths


class ManualStopStore:
    """Presence of ``manual-stop`` means the operator intentionally stopped the App."""

    def __init__(self, home: Path) -> None:
        self.home = home

    def _path(self, name: str) -> Path:
        return ServicePaths(self.home, name).manual_stop()

    def is_manual_stop(self, name: str) -> bool:
        return self._path(name).is_file()

    def mark(self, name: str) -> None:
        path = self._path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    def clear(self, name: str) -> None:
        path = self._path(name)
        if path.is_file():
            path.unlink()
