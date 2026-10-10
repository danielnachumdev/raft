"""Injectable imports for the CLI (patch consumer bindings in tests)."""

from ..config import load_config, setup_logging
from ..models.stack import load_stack
from ..apply import AppApply
from ..auth import GitAuthManager
from ..deploy.orchestrator import Orchestrator
from ..ops.doctor import Doctor
from ..ops.logs import Logs
from ..ops.purge import Purge
from ..ops.status import Status
from ..ops.uninstall import Uninstall
from ..ops.update import SelfUpdate
from ..serve import Serve

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
