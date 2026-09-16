"""High-level operations: apply, sync, auth, cutover, orchestration.

Exports are loaded lazily so adapters can import leaf service modules
(e.g. ``certs``, ``command_errors``) without circular imports through
this package ``__init__``.
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
    "wait_until",
]

_EXPORTS = {
    "AppApply": (".apply", "AppApply"),
    "CheckResult": (".doctor", "CheckResult"),
    "DEPLOY_CUTOVER": (".cutover", "DEPLOY_CUTOVER"),
    "CutoverSession": (".cutover", "CutoverSession"),
    "Doctor": (".doctor", "Doctor"),
    "GitAuthManager": (".auth", "GitAuthManager"),
    "Orchestrator": (".orchestrator", "Orchestrator"),
    "ReadinessStrategy": (".readiness", "ReadinessStrategy"),
    "SelfUpdate": (".update", "SelfUpdate"),
    "SourceSync": (".sync", "SourceSync"),
    "StackRenderer": (".render", "StackRenderer"),
    "wait_until": (".cutover", "wait_until"),
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
