"""Time-stamped chart annotations for serve Trends / Runtime graphs."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class GraphEvent:
    """Generic chart marker (deployment, stop, scaling, …)."""

    kind: str
    ts: str
    service: Optional[str] = None
    label: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None

    def to_mapping(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind, "ts": self.ts}
        if self.id is not None:
            out["id"] = self.id
        if self.service is not None:
            out["service"] = self.service
        if self.label is not None:
            out["label"] = self.label
        if self.metadata:
            out["metadata"] = dict(self.metadata)
        return out

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> Optional["GraphEvent"]:
        kind = data.get("kind")
        ts = data.get("ts")
        if not isinstance(kind, str) or not kind.strip():
            return None
        if not isinstance(ts, str) or not ts.strip():
            return None
        return cls(
            kind=kind.strip(),
            ts=ts.strip(),
            service=cls._opt_str(data.get("service")),
            label=cls._opt_str(data.get("label")),
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
