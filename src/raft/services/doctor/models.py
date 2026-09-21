"""Doctor result model and group constants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Status = Literal["ok", "warn", "fail"]

# Host/platform CheckResult.service bucket (displayed under group RAFT_GROUP).
INFRA = "infra"
# Built-in doctor group for edge containers + host checks.
RAFT_GROUP = "raft"
UNGROUPED = "ungrouped"

# Preferred member order under the raft group (then remaining infra keys alpha).
RAFT_MEMBER_ORDER = (
    "docker",
    "compose.yaml",
    "generated",
    "stack",
    "edge",
)


@dataclass(frozen=True)
class CheckResult:
    service: str
    check: str
    status: Status
    detail: str
    fix: str = ""
