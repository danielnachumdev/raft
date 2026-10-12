"""Subprocess failure classification strategies."""

from .compose import ComposeRule
from .disk_full import DiskFullRule
from .docker_daemon import DockerDaemonRule
from .docker_pull import DockerPullRule
from .git import GitRule
from .host_oom import HostOomRule
from .origin_cert import OriginCertRule
from .port_in_use import PortInUseRule
from .registry_pull import RegistryPullRule
from .rule import SubprocessRule

__all__ = [
    "ComposeRule",
    "DiskFullRule",
    "DockerDaemonRule",
    "DockerPullRule",
    "GitRule",
    "HostOomRule",
    "OriginCertRule",
    "PortInUseRule",
    "RegistryPullRule",
    "SUBPROCESS_STRATEGIES",
    "SubprocessRule",
]

SUBPROCESS_STRATEGIES: tuple = (
    OriginCertRule(),
    HostOomRule(),
    DiskFullRule(),
    RegistryPullRule(),
    DockerDaemonRule(),
    PortInUseRule(),
    ComposeRule(),
    GitRule(),
    DockerPullRule(),
)
