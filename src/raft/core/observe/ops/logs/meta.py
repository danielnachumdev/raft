"""Cursor metadata for one retained service-log stream."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

META_FILENAME = "meta.json"


@dataclass
class ServiceLogsMeta:
    """Last shipped Docker container id + timestamp cursor."""

    container_id: str = ""
    cursor: str = ""
    generation: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "containerId": self.container_id,
            "cursor": self.cursor,
            "generation": self.generation,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ServiceLogsMeta":
        return cls(
            container_id=str(raw.get("containerId") or ""),
            cursor=str(raw.get("cursor") or ""),
            generation=int(raw.get("generation") or 0),
        )


class ServiceLogsMetaStore:
    """Load/save ``meta.json`` beside ``current.log`` (best-effort)."""

    def __init__(self, service_dir: Path) -> None:
        self.path = service_dir / META_FILENAME

    def load(self) -> ServiceLogsMeta:
        if not self.path.is_file():
            return ServiceLogsMeta()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.debug("service-logs meta load failed path=%s err=%s", self.path, exc)
            return ServiceLogsMeta()
        if not isinstance(raw, dict):
            return ServiceLogsMeta()
        return ServiceLogsMeta.from_dict(raw)

    def save(self, meta: ServiceLogsMeta) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        text = json.dumps(meta.to_dict(), separators=(",", ":")) + "\n"
        try:
            self.path.write_text(text, encoding="utf-8")
            self.path.chmod(0o600)
        except OSError as exc:
            logger.debug("service-logs meta save failed path=%s err=%s", self.path, exc)
