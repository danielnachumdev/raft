"""Injectable imports for the CLI (patch `raft.cli.deps.*` in tests)."""

from ..config import load_config, setup_logging
from ..models.stack import load_stack
from ..services.apply import AppApply
from ..services.auth import GitAuthManager
from ..services.deploy.orchestrator import Orchestrator
from ..services.ops.doctor import Doctor
from ..services.ops.logs import Logs
from ..services.ops.status import Status
from ..services.ops.uninstall import Uninstall
from ..services.ops.update import SelfUpdate
from ..services.serve import Serve

__all__ = [
    "AppApply",
    "Doctor",
    "GitAuthManager",
    "Logs",
    "Orchestrator",
    "SelfUpdate",
    "Serve",
    "Status",
    "Uninstall",
    "load_config",
    "load_stack",
    "setup_logging",
]
