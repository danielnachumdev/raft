"""Mutable bag of nginx/Compose fragments produced by edge handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class EdgeFragments:
    router_includes: List[str] = field(default_factory=list)
    router_servers: List[str] = field(default_factory=list)
    gate_http: List[str] = field(default_factory=list)
    gate_stream: List[str] = field(default_factory=list)
    gate_tls: Dict[str, str] = field(default_factory=dict)
    upstreams: Dict[str, str] = field(default_factory=dict)
    host_publish: List[str] = field(default_factory=list)
    expose_ports: List[int] = field(default_factory=list)

    def merge(self, other: "EdgeFragments") -> None:
        self.router_includes.extend(other.router_includes)
        self.router_servers.extend(other.router_servers)
        self.gate_http.extend(other.gate_http)
        self.gate_stream.extend(other.gate_stream)
        self.gate_tls.update(other.gate_tls)
        self.upstreams.update(other.upstreams)
        self.host_publish.extend(other.host_publish)
        self.expose_ports.extend(other.expose_ports)
