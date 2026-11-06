"""CLI import registry. Resolution lives in :class:`LazyImportManager`."""

from __future__ import annotations

from .lazy_import import LazyImportManager

CLI_IMPORTS = LazyImportManager(
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
