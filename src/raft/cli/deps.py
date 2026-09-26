"""Injectable imports for the CLI (patch `raft.cli.deps.*` in tests)."""

from ..config import load_config, setup_logging
from ..models import load_stack
from ..services.apply import AppApply
from ..services.auth import GitAuthManager
from ..services.deploy.orchestrator import Orchestrator
from ..services.ops.doctor import Doctor
from ..services.ops.stats import Stats
from ..services.ops.uninstall import Uninstall
from ..services.ops.update import SelfUpdate

__all__ = [
    "AppApply",
    "Doctor",
    "GitAuthManager",
    "Orchestrator",
    "SelfUpdate",
    "Stats",
    "Uninstall",
    "load_config",
    "load_stack",
    "setup_logging",
]
