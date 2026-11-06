"""Lazy CLI dependency registry (``module:attr`` strings, one loader)."""

from __future__ import annotations

import importlib
from typing import Any, Optional

# Names tests patch are bound on the command modules that import these callables.
_REGISTRY = {
    "AppApply": "raft.core.lifecycle.apply:AppApply",
    "Doctor": "raft.core.observe.ops.doctor:Doctor",
    "GetCLI": "raft.services.cli.commands.get:GetCLI",
    "GitAuthManager": "raft.core.platform.auth:GitAuthManager",
    "HostLogging": "raft.core.core.utils:HostLogging",
    "Logs": "raft.core.observe.ops.logs:Logs",
    "Orchestrator": "raft.core.lifecycle.deploy.orchestrator:Orchestrator",
    "Purge": "raft.core.observe.ops.purge:Purge",
    "SelfUpdate": "raft.core.observe.ops.update:SelfUpdate",
    "Serve": "raft.services.serve:Serve",
    "ServiceActions": "raft.core.observe.ops.actions:ServiceActions",
    "SettingsLoader": "raft.core.core.config:SettingsLoader",
    "Status": "raft.core.observe.ops.status:Status",
    "Uninstall": "raft.core.observe.ops.uninstall:Uninstall",
    "load_stack": "raft.core.core.models.stack:load_stack",
    "AlertsCLI": "raft.services.cli.commands.alerts:AlertsCLI",
    "AuthCLI": "raft.services.cli.commands.auth:AuthCLI",
    "DbCLI": "raft.services.cli.commands.db:DbCLI",
    "EventsCLI": "raft.services.cli.commands.events:EventsCLI",
    "FirewallCLI": "raft.services.cli.commands.firewall:FirewallCLI",
    "GithubCLI": "raft.services.cli.commands.github:GithubCLI",
    "HttpRequestsCLI": "raft.services.cli.commands.http_requests:HttpRequestsCLI",
    "MetricsCLI": "raft.services.cli.commands.metrics:MetricsCLI",
    "NotificationsCLI": "raft.services.cli.commands.notifications:NotificationsCLI",
}


def load(name: str) -> Any:
    """Import and return the object registered under ``name``."""
    module_name, attr = _REGISTRY[name].split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, attr)


class _Lazy:
    """Callable stand-in. Resolves through :func:`load` when called."""

    def __init__(self, name: str) -> None:
        self._name = name

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return load(self._name)(*args, **kwargs)


class _LazyGroup:
    """Fire group. The real sub-CLI is imported on first use."""

    _dep = ""

    def __init__(self, stack: Any) -> None:
        self._stack = stack
        self._obj: Any = None

    def _target(self) -> Any:
        if self._obj is None:
            self._obj = load(self._dep)(self._stack)
        return self._obj

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target(), name)

    def __dir__(self) -> list[str]:
        return dir(self._target())


class _EventsGroup(_LazyGroup):
    """Callable ``raft events`` group (same signature as ``EventsCLI``)."""

    _dep = "EventsCLI"
    __doc__ = "List the durable operator system event journal (#267)."

    def __call__(
        self,
        hours: int = 24,
        service: Optional[str] = None,
        kind: Optional[str] = None,
        limit: int = 200,
        json: bool = False,
    ) -> None:
        """Print recent ops events (same journal as serve Events)."""
        self._target()(
            hours=hours,
            service=service,
            kind=kind,
            limit=limit,
            json=json,
        )


def _group(dep: str, doc: str) -> type:
    return type(dep, (_LazyGroup,), {"_dep": dep, "__doc__": doc})


_GROUP_TYPES = {
    "alerts": _group("AlertsCLI", "Manage alert rules under ``host/alerts.yaml``."),
    "auth": _group(
        "AuthCLI",
        "Manage per-service read-only SSH deploy keys for private git sources.",
    ),
    "db": _group("DbCLI", "Schema upgrade and migrate-from-files for ``raft.sqlite`` (#317)."),
    "events": _EventsGroup,
    "firewall": _group(
        "FirewallCLI",
        "Manage ordered gate firewall rules under ``host/firewall.yaml``.",
    ),
    "github": _group(
        "GithubCLI",
        "GitHub OAuth assist / deploy (same ``GithubAssistService`` as serve).",
    ),
    "http_requests": _group(
        "HttpRequestsCLI",
        "List recent gate access.log rows for one Host-routed App.",
    ),
    "metrics": _group(
        "MetricsCLI",
        "Historical metrics query and catalog exports (same cores as serve).",
    ),
    "notifications": _group(
        "NotificationsCLI",
        "Manage channels in ``~/.raft/host/notifications.yaml``.",
    ),
}

GROUP_NAMES = frozenset(_GROUP_TYPES)


def lazy_group(name: str, stack: Any) -> _LazyGroup:
    """Return the dispatched Fire group without importing sibling commands."""
    return _GROUP_TYPES[name](stack)


AppApply = _Lazy("AppApply")
Doctor = _Lazy("Doctor")
GetCLI = _Lazy("GetCLI")
GitAuthManager = _Lazy("GitAuthManager")
HostLogging = _Lazy("HostLogging")
Logs = _Lazy("Logs")
Orchestrator = _Lazy("Orchestrator")
Purge = _Lazy("Purge")
SelfUpdate = _Lazy("SelfUpdate")
Serve = _Lazy("Serve")
ServiceActions = _Lazy("ServiceActions")
SettingsLoader = _Lazy("SettingsLoader")
Status = _Lazy("Status")
Uninstall = _Lazy("Uninstall")
load_stack = _Lazy("load_stack")

__all__ = [
    "AppApply",
    "Doctor",
    "GROUP_NAMES",
    "GetCLI",
    "GitAuthManager",
    "HostLogging",
    "Logs",
    "Orchestrator",
    "Purge",
    "SelfUpdate",
    "Serve",
    "ServiceActions",
    "SettingsLoader",
    "Status",
    "Uninstall",
    "lazy_group",
    "load",
    "load_stack",
]
