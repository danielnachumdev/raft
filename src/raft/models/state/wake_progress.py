"""Last known scale-wake stage for controller diagnostic logs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class WakeProgress:
    """Opaque-id companion: where wake stopped (not shown to visitors)."""

    stage: str
    service: Optional[str] = None
    detail: Optional[str] = None

    def log_tail(self) -> str:
        parts = [f"stage={self.stage}"]
        if self.service:
            parts.append(f"service={self.service}")
        if self.detail:
            parts.append(f"detail={self.detail}")
        return " ".join(parts)

    def to_mapping(self) -> dict[str, Any]:
        out: dict[str, Any] = {"stage": self.stage}
        if self.service:
            out["service"] = self.service
        if self.detail:
            out["detail"] = self.detail
        return out

    @classmethod
    def from_mapping(cls, data: Any) -> Optional["WakeProgress"]:
        if not isinstance(data, dict):
            return None
        stage = data.get("stage")
        if not isinstance(stage, str) or not stage.strip():
            return None
        return cls(
            stage=stage.strip(),
            service=cls._opt(data.get("service")),
            detail=cls._opt(data.get("detail")),
        )

    @staticmethod
    def _opt(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
