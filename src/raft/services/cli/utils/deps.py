"""Deferred CLI constructors. Each name is one :class:`LazyImport`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .lazy_import import LazyImport

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
    from raft.services.cli.commands import RaftCLICommands
    from raft.services.cli.commands.alerts import AlertsCLI
    from raft.services.cli.commands.auth import AuthCLI
    from raft.services.cli.commands.db import DbCLI
    from raft.services.cli.commands.events import EventsCLI
    from raft.services.cli.commands.firewall import FirewallCLI
    from raft.services.cli.commands.get import GetCLI
    from raft.services.cli.commands.github import GithubCLI
    from raft.services.cli.commands.http_requests import HttpRequestsCLI
    from raft.services.cli.commands.metrics import MetricsCLI
    from raft.services.cli.commands.notifications import NotificationsCLI
    from raft.services.cli.exit_mapper import CliExitMapper
    from raft.services.serve import Serve
else:
    AlertsCLI = LazyImport("raft.services.cli.commands.alerts", "AlertsCLI")
    AppApply = LazyImport("raft.core.lifecycle.apply", "AppApply")
    AuthCLI = LazyImport("raft.services.cli.commands.auth", "AuthCLI")
    CliExitMapper = LazyImport("raft.services.cli.exit_mapper", "CliExitMapper")
    DbCLI = LazyImport("raft.services.cli.commands.db", "DbCLI")
    Doctor = LazyImport("raft.core.observe.ops.doctor", "Doctor")
    EventsCLI = LazyImport("raft.services.cli.commands.events", "EventsCLI")
    FirewallCLI = LazyImport("raft.services.cli.commands.firewall", "FirewallCLI")
    GetCLI = LazyImport("raft.services.cli.commands.get", "GetCLI")
    GitAuthManager = LazyImport("raft.core.platform.auth", "GitAuthManager")
    GithubCLI = LazyImport("raft.services.cli.commands.github", "GithubCLI")
    HostLogging = LazyImport("raft.core.core.utils", "HostLogging")
    HttpRequestsCLI = LazyImport("raft.services.cli.commands.http_requests", "HttpRequestsCLI")
    Logs = LazyImport("raft.core.observe.ops.logs", "Logs")
    MetricsCLI = LazyImport("raft.services.cli.commands.metrics", "MetricsCLI")
    NotificationsCLI = LazyImport("raft.services.cli.commands.notifications", "NotificationsCLI")
    Orchestrator = LazyImport("raft.core.lifecycle.deploy.orchestrator", "Orchestrator")
    Purge = LazyImport("raft.core.observe.ops.purge", "Purge")
    RaftCLI = LazyImport("raft.services.cli.cli", "RaftCLI")
    RaftCLICommands = LazyImport("raft.services.cli.commands", "RaftCLICommands")
    SelfUpdate = LazyImport("raft.core.observe.ops.update", "SelfUpdate")
    Serve = LazyImport("raft.services.serve", "Serve")
    ServiceActions = LazyImport("raft.core.observe.ops.actions", "ServiceActions")
    SettingsLoader = LazyImport("raft.core.core.config", "SettingsLoader")
    Status = LazyImport("raft.core.observe.ops.status", "Status")
    Uninstall = LazyImport("raft.core.observe.ops.uninstall", "Uninstall")
    load_stack = LazyImport("raft.core.core.models.stack", "load_stack")
