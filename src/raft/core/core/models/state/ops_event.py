"""Time-stamped operator system events (CLI + serve timeline)."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class OpsEvent:
    """PII-safe journal row for the host ops timeline (#267)."""

    kind: str
    ts: str
    summary: str
    service: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None

    def to_mapping(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": self.kind,
            "ts": self.ts,
            "summary": self.summary,
        }
        if self.id is not None:
            out["id"] = self.id
        if self.service is not None:
            out["service"] = self.service
        if self.metadata:
            out["metadata"] = dict(self.metadata)
        return out

    def to_public(self) -> dict[str, Any]:
        """Stable JSON shape for CLI ``--json`` and serve ``/api/events``."""
        return self.to_mapping()

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> Optional["OpsEvent"]:
        kind = data.get("kind")
        ts = data.get("ts")
        summary = data.get("summary")
        if not isinstance(kind, str) or not kind.strip():
            return None
        if not isinstance(ts, str) or not ts.strip():
            return None
        if not isinstance(summary, str):
            summary = ""
        return cls(
            kind=kind.strip(),
            ts=ts.strip(),
            summary=summary.strip(),
            service=cls._opt_str(data.get("service")),
            metadata=cls._as_dict(data.get("metadata")),
            id=cls._opt_str(data.get("id")),
        )

    @staticmethod
    def _opt_str(value: Any) -> Optional[str]:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}
