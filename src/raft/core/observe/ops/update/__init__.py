"""Re-install the raft CLI from GitHub (`raft update`)."""

from .announce import UpdateAnnounce
from .check import UpdateCheck, UpdateCheckResult
from .host_apply import HostApplyGate
from .identity import InstallIdentity
from .latest import LatestRelease, LatestReleaseFetcher
from .outcome import NEXT_STEPS, UpdateOutcome
from .semver import SemverParts
from .service import DEFAULT_INSTALL_URL, SelfUpdate

__all__ = [
    "DEFAULT_INSTALL_URL",
    "HostApplyGate",
    "InstallIdentity",
    "LatestRelease",
    "LatestReleaseFetcher",
    "NEXT_STEPS",
    "SelfUpdate",
    "SemverParts",
    "UpdateAnnounce",
    "UpdateCheck",
    "UpdateCheckResult",
    "UpdateOutcome",
]
