"""External process and edge adapters (docker, nginx, HTTP, shell)."""

from .docker import DockerStack
from .http import HttpProbe
from .nginx import NginxUpstreams
from .shell import Shell

__all__ = [
    "DockerStack",
    "HttpProbe",
    "NginxUpstreams",
    "Shell",
]
