"""Injectable imports for the CLI (patch consumer bindings in tests)."""

from raft.core.core.config import SettingsLoader
from raft.core.core.utils import HostLogging
from raft.core.core.models.stack import load_stack
from raft.core.lifecycle.apply import AppApply
from raft.core.platform.auth import GitAuthManager
from raft.core.lifecycle.deploy.orchestrator import Orchestrator
from raft.core.observe.ops.doctor import Doctor
from raft.core.observe.ops.logs import Logs
from raft.core.observe.ops.purge import Purge
from raft.core.observe.ops.status import Status
from raft.core.observe.ops.uninstall import Uninstall
from raft.core.observe.ops.update import SelfUpdate
from raft.services.serve import Serve

__all__ = [
    "AppApply",
    "Doctor",
    "GitAuthManager",
    "Logs",
    "Orchestrator",
    "Purge",
    "SelfUpdate",
    "Serve",
    "Status",
    "Uninstall",
    "SettingsLoader",
    "load_stack",
    "HostLogging",
]
