"""External process and edge adapters (docker, nginx, HTTP, shell)."""

from .docker import DockerStack
from .host import HostResources, collect_host_resources
from .http import HttpProbe
from .nginx import NginxUpstreams
from .shell import Shell

__all__ = [
    "DockerStack",
    "HostResources",
    "HttpProbe",
    "NginxUpstreams",
    "Shell",
    "collect_host_resources",
]
