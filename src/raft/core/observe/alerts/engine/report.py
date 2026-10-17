"""Evaluation and dry-run report shapes."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class EvaluationReport:
    started_at: datetime
    finished_at: datetime
    rules_total: int = 0
    rules_evaluated: int = 0
    rules_skipped_disabled: int = 0
    notifications_sent: int = 0
    errors: List[Dict[str, str]] = field(default_factory=list)
    document_error: Optional[str] = None

    def to_public(self) -> Dict[str, Any]:
        duration_ms = int(
            (self.finished_at - self.started_at).total_seconds() * 1000
        )
        return {
            "startedAt": self.started_at.isoformat(),
            "finishedAt": self.finished_at.isoformat(),
            "durationMs": duration_ms,
            "rulesTotal": self.rules_total,
            "rulesEvaluated": self.rules_evaluated,
            "rulesSkippedDisabled": self.rules_skipped_disabled,
            "notificationsSent": self.notifications_sent,
            "errors": list(self.errors)[:50],
            "documentError": self.document_error,
        }


@dataclass
class DryRunReport:
    rule_id: str
    evaluated_at: datetime
    error: Optional[str] = None
    subjects: List[Dict[str, Any]] = field(default_factory=list)

    def to_public(self) -> Dict[str, Any]:
        return {
            "ruleId": self.rule_id,
            "evaluatedAt": self.evaluated_at.isoformat(),
            "error": self.error,
            "subjects": list(self.subjects),
        }
