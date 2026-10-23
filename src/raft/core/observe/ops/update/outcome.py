"""Structured result of ``raft update`` / serve apply."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

NEXT_STEPS = (
    "Next: align the running stack with this release — templates and "
    "Compose ids can change. Typical path: `raft render`, then "
    "`raft redeploy <app|router|dashboard|controller>` for targeted "
    "updates, or `raft down && raft up` when edge/service names or "
    "schemas shifted. Finish with `raft doctor`. "
    "`raft redeploy dashboard` / `raft redeploy controller` rebuild "
    "those images with the new install stamp (dashboard: do not flip "
    "dashboard.enabled; controller: brief control-loop gap / mid-flight "
    "jobs). Restart `raft serve` if you use it."
)


@dataclass(frozen=True)
class UpdateOutcome:
    """Result after reinstall finishes (CLI announce + serve JSON)."""

    already_current: bool
    before_line: Optional[str]
    after_line: Optional[str]

    def next_steps(self) -> Optional[str]:
        return None if self.already_current else NEXT_STEPS

    def as_public(self) -> dict:
        return {
            "alreadyCurrent": self.already_current,
            "beforeLine": self.before_line,
            "afterLine": self.after_line,
            "nextSteps": self.next_steps(),
        }
