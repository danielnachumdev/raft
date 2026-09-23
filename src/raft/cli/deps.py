"""Injectable imports for the CLI (patch `raft.cli.deps.*` in tests)."""

from ..config import load_config, setup_logging
from ..models import load_stack
from ..services import Doctor, GitAuthManager, Orchestrator, SelfUpdate
from ..services.apply import AppApply
from ..services.stats import Stats
from ..services.uninstall import Uninstall

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
