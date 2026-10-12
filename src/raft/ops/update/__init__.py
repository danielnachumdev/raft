"""Re-install the raft CLI from GitHub (`raft update`)."""

from .identity import InstallIdentity
from .service import DEFAULT_INSTALL_URL, SelfUpdate

__all__ = ["DEFAULT_INSTALL_URL", "InstallIdentity", "SelfUpdate"]
