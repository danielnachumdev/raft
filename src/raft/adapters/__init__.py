"""External process and edge adapters (docker, nginx, HTTP, shell)."""

from .docker import ContainerRuntimeGateway, ContainerRuntimeRow, DockerStack
from .host import DockerStatsText, HostGateway, HostProbe, HostResources
from .http import HttpProbe
from .nginx import NginxUpstreams, NginxUpstreamText
from .shell import Shell

__all__ = [
    "ContainerRuntimeGateway",
    "ContainerRuntimeRow",
    "DockerStack",
    "DockerStatsText",
    "HostGateway",
    "HostProbe",
    "HostResources",
    "HttpProbe",
    "NginxUpstreamText",
    "NginxUpstreams",
    "Shell",
]
