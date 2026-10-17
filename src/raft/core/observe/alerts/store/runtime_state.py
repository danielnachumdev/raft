"""Runtime instance and evaluation state dataclasses."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class AlertInstanceState:
    rule_id: str
    subject: str
    rule_hash: str
    state: str  # pending | firing
    pending_since: Optional[datetime] = None
    firing_since: Optional[datetime] = None
    last_notified_at: Optional[datetime] = None
    last_resolved_at: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    suppressed: bool = False
    last_evaluated_at: Optional[datetime] = None
    last_values: List[Dict[str, Any]] = field(default_factory=list)

    def to_mapping(self) -> Dict[str, Any]:
        return {
            "ruleId": self.rule_id,
            "subject": self.subject,
            "ruleHash": self.rule_hash,
            "state": self.state,
            "pendingSince": _iso(self.pending_since),
            "firingSince": _iso(self.firing_since),
            "lastNotifiedAt": _iso(self.last_notified_at),
            "lastResolvedAt": _iso(self.last_resolved_at),
            "cooldownUntil": _iso(self.cooldown_until),
            "suppressed": self.suppressed,
            "lastEvaluatedAt": _iso(self.last_evaluated_at),
            "lastValues": list(self.last_values),
        }

    @classmethod
    def from_mapping(cls, raw: Dict[str, Any]) -> "AlertInstanceState":
        return cls(
            rule_id=str(raw.get("ruleId") or ""),
            subject=str(raw.get("subject") or "-"),
            rule_hash=str(raw.get("ruleHash") or ""),
            state=str(raw.get("state") or "pending"),
            pending_since=_parse(raw.get("pendingSince")),
            firing_since=_parse(raw.get("firingSince")),
            last_notified_at=_parse(raw.get("lastNotifiedAt")),
            last_resolved_at=_parse(raw.get("lastResolvedAt")),
            cooldown_until=_parse(raw.get("cooldownUntil")),
            suppressed=bool(raw.get("suppressed")),
            last_evaluated_at=_parse(raw.get("lastEvaluatedAt")),
            last_values=list(raw.get("lastValues") or []),
        )


@dataclass
class AlertRuntime:
    version: int = 1
    last_evaluation: Optional[Dict[str, Any]] = None
    instances: Dict[str, AlertInstanceState] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "AlertRuntime":
        return cls()

    def to_mapping(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "lastEvaluation": self.last_evaluation,
            "instances": {k: v.to_mapping() for k, v in self.instances.items()},
        }

    @classmethod
    def from_mapping(cls, raw: Dict[str, Any]) -> "AlertRuntime":
        instances = {}
        for key, value in (raw.get("instances") or {}).items():
            if isinstance(value, dict):
                instances[str(key)] = AlertInstanceState.from_mapping(value)
        return cls(
            version=int(raw.get("version") or 1),
            last_evaluation=raw.get("lastEvaluation"),
            instances=instances,
        )


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _parse(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
