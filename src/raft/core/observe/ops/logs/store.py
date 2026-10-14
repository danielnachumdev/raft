"""On-disk retained service stdout under ``state/service-logs/<key>/``."""

import logging
from pathlib import Path
from typing import Optional

from raft.core.core.utils import LogRotationBootstrap

from .meta import ServiceLogsMeta, ServiceLogsMetaStore

logger = logging.getLogger(__name__)

SERVICE_LOGS_DIR = Path("state") / "service-logs"
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
    ) -> None:
        self.home = home
        self._rotation = rotation or LogRotationBootstrap(
            max_age_days=max_age_days,
            max_bytes=max_bytes,
        )

    def root(self) -> Path:
        return self.home / SERVICE_LOGS_DIR

    def service_dir(self, key: str) -> Path:
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
