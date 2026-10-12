"""Nginx upstream file helpers."""

from .upstream_text import NginxUpstreamText
from .upstreams import NginxUpstreams

__all__ = [
    "NginxUpstreamText",
    "NginxUpstreams",
]
