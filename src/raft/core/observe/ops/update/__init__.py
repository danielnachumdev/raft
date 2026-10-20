"""Re-install the raft CLI from GitHub (`raft update`)."""

from .announce import UpdateAnnounce
from .check import UpdateCheck, UpdateCheckResult
from .host_apply import HostApplyGate
from .host_docker import HostDockerUpdate
from .identity import InstallIdentity
from .install_cmd import DEFAULT_HOST_UPDATE_IMAGE, DEFAULT_INSTALL_URL, InstallCmd
from .latest import LatestRelease, LatestReleaseFetcher
from .outcome import NEXT_STEPS, UpdateOutcome
from .semver import SemverParts
from .service import SelfUpdate

__all__ = [
    "DEFAULT_HOST_UPDATE_IMAGE",
    "DEFAULT_INSTALL_URL",
    "HostApplyGate",
    "HostDockerUpdate",
    "InstallCmd",
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
