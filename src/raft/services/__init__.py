"""High-level operations: apply, sync, auth, cutover, orchestration.

Exports are loaded lazily so adapters can import leaf service modules
(e.g. ``certs``) without circular imports through this package ``__init__``.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "AppApply",
    "CheckResult",
    "DEPLOY_CUTOVER",
    "CutoverSession",
    "Doctor",
    "GitAuthManager",
    "Orchestrator",
    "ReadinessStrategy",
    "SelfUpdate",
    "SourceSync",
    "StackRenderer",
    "Stats",
    "Uninstall",
    "wait_until",
]

_EXPORTS = {
    "AppApply": (".apply", "AppApply"),
    "CheckResult": (".ops.doctor", "CheckResult"),
    "DEPLOY_CUTOVER": (".deploy.cutover", "DEPLOY_CUTOVER"),
    "CutoverSession": (".deploy.cutover", "CutoverSession"),
    "Doctor": (".ops.doctor", "Doctor"),
    "GitAuthManager": (".auth", "GitAuthManager"),
    "Orchestrator": (".deploy.orchestrator", "Orchestrator"),
    "ReadinessStrategy": (".deploy.readiness", "ReadinessStrategy"),
    "SelfUpdate": (".ops.update", "SelfUpdate"),
    "SourceSync": (".sync", "SourceSync"),
    "StackRenderer": (".render", "StackRenderer"),
    "Stats": (".ops.stats", "Stats"),
    "Uninstall": (".ops.uninstall", "Uninstall"),
    "wait_until": (".deploy.wait", "wait_until"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, attr)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
