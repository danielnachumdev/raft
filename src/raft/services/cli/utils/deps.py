"""CLI import registry. Resolution lives in :class:`LazyImportManager`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .lazy_import import LazyImportManager

lazy = LazyImportManager(
    targets={
        "AppApply": "raft.core.lifecycle.apply:AppApply",
        "CliExitMapper": "raft.services.cli.exit_mapper:CliExitMapper",
        "Doctor": "raft.core.observe.ops.doctor:Doctor",
        "GetCLI": "raft.services.cli.commands.get:GetCLI",
        "GitAuthManager": "raft.core.platform.auth:GitAuthManager",
        "HostLogging": "raft.core.core.utils:HostLogging",
        "Logs": "raft.core.observe.ops.logs:Logs",
        "Orchestrator": "raft.core.lifecycle.deploy.orchestrator:Orchestrator",
        "Purge": "raft.core.observe.ops.purge:Purge",
        "RaftCLI": "raft.services.cli.cli:RaftCLI",
        "RaftCLICommands": "raft.services.cli.commands:RaftCLICommands",
        "SelfUpdate": "raft.core.observe.ops.update:SelfUpdate",
        "Serve": "raft.services.serve:Serve",
        "ServiceActions": "raft.core.observe.ops.actions:ServiceActions",
        "SettingsLoader": "raft.core.core.config:SettingsLoader",
        "Status": "raft.core.observe.ops.status:Status",
        "Uninstall": "raft.core.observe.ops.uninstall:Uninstall",
        "load_stack": "raft.core.core.models.stack:load_stack",
    },
    commands={
        "alerts": (
            "raft.services.cli.commands.alerts:AlertsCLI",
            "Manage alert rules under ``host/alerts.yaml``.",
        ),
        "auth": (
            "raft.services.cli.commands.auth:AuthCLI",
            "Manage per-service read-only SSH deploy keys for private git sources.",
        ),
        "db": (
            "raft.services.cli.commands.db:DbCLI",
            "Schema upgrade and migrate-from-files for ``raft.sqlite`` (#317).",
        ),
        "events": (
            "raft.services.cli.commands.events:EventsCLI",
            "List the durable operator system event journal (#267).",
        ),
        "firewall": (
            "raft.services.cli.commands.firewall:FirewallCLI",
            "Manage ordered gate firewall rules under ``host/firewall.yaml``.",
        ),
        "github": (
            "raft.services.cli.commands.github:GithubCLI",
            "GitHub OAuth assist / deploy (same ``GithubAssistService`` as serve).",
        ),
        "http_requests": (
            "raft.services.cli.commands.http_requests:HttpRequestsCLI",
            "List recent gate access.log rows for one Host-routed App.",
        ),
        "metrics": (
            "raft.services.cli.commands.metrics:MetricsCLI",
            "Historical metrics query and catalog exports (same cores as serve).",
        ),
        "notifications": (
            "raft.services.cli.commands.notifications:NotificationsCLI",
            "Manage channels in ``~/.raft/host/notifications.yaml``.",
        ),
    },
    callable_commands=frozenset({"events"}),
)

if TYPE_CHECKING:
    from raft.core.core.config import SettingsLoader
    from raft.core.core.models.stack import load_stack
    from raft.core.core.utils import HostLogging
    from raft.core.lifecycle.apply import AppApply
    from raft.core.lifecycle.deploy.orchestrator import Orchestrator
    from raft.core.observe.ops.actions import ServiceActions
    from raft.core.observe.ops.doctor import Doctor
    from raft.core.observe.ops.logs import Logs
    from raft.core.observe.ops.purge import Purge
    from raft.core.observe.ops.status import Status
    from raft.core.observe.ops.uninstall import Uninstall
    from raft.core.observe.ops.update import SelfUpdate
    from raft.core.platform.auth import GitAuthManager
    from raft.services.cli.cli import RaftCLI
    from raft.services.cli.commands.get import GetCLI
    from raft.services.serve import Serve
else:
    AppApply = lazy.bind("AppApply")
    Doctor = lazy.bind("Doctor")
    GetCLI = lazy.bind("GetCLI")
    GitAuthManager = lazy.bind("GitAuthManager")
    HostLogging = lazy.bind("HostLogging")
    Logs = lazy.bind("Logs")
    Orchestrator = lazy.bind("Orchestrator")
    Purge = lazy.bind("Purge")
    RaftCLI = lazy.bind("RaftCLI")
    SelfUpdate = lazy.bind("SelfUpdate")
    Serve = lazy.bind("Serve")
    ServiceActions = lazy.bind("ServiceActions")
    SettingsLoader = lazy.bind("SettingsLoader")
    Status = lazy.bind("Status")
    Uninstall = lazy.bind("Uninstall")
    load_stack = lazy.bind("load_stack")
