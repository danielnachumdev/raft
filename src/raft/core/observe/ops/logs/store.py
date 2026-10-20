"""On-disk retained service stdout under ``services/<name>/logs/`` (#313)."""

import logging
from pathlib import Path
from typing import Mapping, Optional

from raft.core.core.config.paths.constants import HOST_EDGE_SERVICE_LOGS_DIR
from raft.core.core.config.paths.host_paths import HostPaths
from raft.core.core.config.paths.service_paths import ServicePaths
from raft.core.core.utils import LogRotationBootstrap

from .meta import ServiceLogsMeta, ServiceLogsMetaStore

logger = logging.getLogger(__name__)

# Edge/control-plane retained logs; applied Apps use ``services/<name>/logs/``.
SERVICE_LOGS_DIR = HOST_EDGE_SERVICE_LOGS_DIR
CURRENT_LOG_NAME = "current.log"
GENERATION_MARKER = "--- raft: generation container={short} ---"


class ServiceLogsStore:
    """Append-only retained log files with rotation + meta cursor."""

    def __init__(
        self,
        home: Path,
        *,
        max_age_days: int,
        max_bytes: int,
        rotation: Optional[LogRotationBootstrap] = None,
        compose_to_app: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.home = home
        self._rotation = rotation or LogRotationBootstrap(
            max_age_days=max_age_days,
            max_bytes=max_bytes,
        )
        self._compose_to_app = dict(compose_to_app or {})

    def root(self) -> Path:
        """Edge retained-logs root (applied Apps use per-service dirs)."""
        return HostPaths(self.home).edge_service_logs()

    def service_dir(self, key: str) -> Path:
        app_name = self._compose_to_app.get(key) or self._compose_to_app.get(
            key.split("-", 1)[-1] if "-" in key else key
        )
        if app_name is None and (self.home / "services" / key / "app.yaml").is_file():
            app_name = key
        if app_name is not None:
            return ServicePaths(self.home, app_name).logs()
        return self.root() / key

    def active_path(self, key: str) -> Path:
        return self.service_dir(key) / CURRENT_LOG_NAME

    def load_meta(self, key: str) -> ServiceLogsMeta:
        return ServiceLogsMetaStore(self.service_dir(key)).load()

    def save_meta(self, key: str, meta: ServiceLogsMeta) -> None:
        ServiceLogsMetaStore(self.service_dir(key)).save(meta)

    def append_lines(self, key: str, lines: list[str]) -> None:
        """Rotate if needed, then append plain-text lines (no trailing blank)."""
        if not lines:
            return
        active = self.active_path(key)
        active.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._rotation.prepare(active)
        chunk = "\n".join(lines) + "\n"
        try:
            with active.open("a", encoding="utf-8") as handle:
                handle.write(chunk)
            active.chmod(0o600)
        except OSError as exc:
            logger.warning(
                "service-logs append failed key=%s path=%s err=%s",
                key,
                active,
                exc,
            )
            raise

    def note_generation(self, key: str, container_id: str) -> None:
        short = container_id[:12] if container_id else "unknown"
        self.append_lines(key, [GENERATION_MARKER.format(short=short)])

    def bind_apps(self, apps) -> None:
        self._compose_to_app = self.compose_map_from_apps(apps)

    @staticmethod
    def compose_map_from_apps(apps) -> dict[str, str]:
        """Map compose_id and metadata.name → service directory name."""
        out: dict[str, str] = {}
        for app in apps:
            out[app.compose_id] = app.name
            out[app.name] = app.name
        return out
