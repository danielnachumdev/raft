"""External process and edge adapters (docker, nginx, HTTP, shell)."""

from .docker import DockerStack
from .host import DockerStatsText, HostProbe, HostResources
from .http import HttpProbe
from .nginx import NginxUpstreams, NginxUpstreamText
from .shell import Shell

__all__ = [
    "DockerStack",
    "DockerStatsText",
    "HostProbe",
    "HostResources",
    "HttpProbe",
    "NginxUpstreamText",
    "NginxUpstreams",
    "Shell",
]
