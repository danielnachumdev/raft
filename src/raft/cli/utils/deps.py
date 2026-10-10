"""Injectable imports for the CLI (patch consumer bindings in tests)."""

from raft.config import load_config, setup_logging
from raft.models.stack import load_stack
from raft.apply import AppApply
from raft.auth import GitAuthManager
from raft.deploy.orchestrator import Orchestrator
from raft.ops.doctor import Doctor
from raft.ops.logs import Logs
from raft.ops.purge import Purge
from raft.ops.status import Status
from raft.ops.uninstall import Uninstall
from raft.ops.update import SelfUpdate
from raft.serve import Serve

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
    "load_config",
    "load_stack",
    "setup_logging",
]
