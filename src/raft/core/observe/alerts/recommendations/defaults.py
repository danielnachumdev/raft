"""Raw default alert recommendation specs (data only)."""

from typing import Any, Dict, List

from raft.core.observe.ops.status.models import STATUS_CRASH_LOOPING, STATUS_NOT_RUNNING

_OOM: Dict[str, Any] = {
    "id": "any-service-oom",
    "kind": "state",
    "title": "Alert when any service is OOM-killed / crash-looping",
    "summary": (
        "Watch control.container_status for every App (target *). "
        f"Match state in [{STATUS_CRASH_LOOPING}] — covers OOMKilled "
        "and restart churn via CrashLoopDetector."
    ),
    "rule_id": "any-service-oom",
    "name": "Any service OOM / crash-loop",
    "severity": "critical",
    "description": (
        "Fires when any App container is crash-looping. "
        "Raft maps Docker OOMKilled into that status."
    ),
    "for": "0s",
    "signal": "control.container_status",
    "select": {"target": "*"},
    "kind_id": "state",
    "params": {"match": "in", "values": [STATUS_CRASH_LOOPING]},
}

_NOT_RUNNING: Dict[str, Any] = {
    "id": "any-service-not-running",
    "kind": "state",
    "title": "Alert when any service is not running",
    "summary": (
        "Watch control.container_status for every App (target *). "
        f"Match state in [{STATUS_NOT_RUNNING}, exited, dead] for 2m. "
        "Scaled-to-zero Apps are skipped by the signal source."
    ),
    "rule_id": "any-service-not-running",
    "name": "Any service not running",
    "severity": "error",
    "description": (
        "Fires when any App container is not running "
        "(excludes intentional scale-to-zero)."
    ),
    "for": "2m",
    "signal": "control.container_status",
    "select": {"target": "*"},
    "kind_id": "state",
    "params": {
        "match": "in",
        "values": [STATUS_NOT_RUNNING, "exited", "dead"],
    },
}

_HIGH_MEMORY: Dict[str, Any] = {
    "id": "any-service-high-memory",
    "kind": "threshold",
    "title": "Alert when any service uses high memory",
    "summary": (
        "Watch metrics.resources memory_used_percent for every App "
        "(target *). Threshold avg over 5m > 90%."
    ),
    "rule_id": "any-service-high-memory",
    "name": "Any service high memory",
    "severity": "warning",
    "description": "Fires when any App averages above 90% memory for 5m.",
    "for": "0s",
    "signal": "metrics.resources",
    "select": {"target": "*", "metric": "memory_used_percent"},
    "kind_id": "threshold",
    "params": {"aggregate": "avg", "window": "5m", "op": "gt", "value": 90},
}


def default_specs() -> List[Dict[str, Any]]:
    return [_OOM, _NOT_RUNNING, _HIGH_MEMORY]
