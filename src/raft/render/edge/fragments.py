"""Mutable bag of nginx/Compose fragments produced by edge handlers."""

from dataclasses import dataclass, field


@dataclass
class EdgeFragments:
    router_includes: list[str] = field(default_factory=list)
    router_servers: list[str] = field(default_factory=list)
    gate_http: list[str] = field(default_factory=list)
    gate_stream: list[str] = field(default_factory=list)
    gate_tls: dict[str, str] = field(default_factory=dict)
    upstreams: dict[str, str] = field(default_factory=dict)
    host_publish: list[str] = field(default_factory=list)
    expose_ports: list[int] = field(default_factory=list)

    def merge(self, other: "EdgeFragments") -> None:
        self.router_includes.extend(other.router_includes)
        self.router_servers.extend(other.router_servers)
        self.gate_http.extend(other.gate_http)
        self.gate_stream.extend(other.gate_stream)
        self.gate_tls.update(other.gate_tls)
        self.upstreams.update(other.upstreams)
        self.host_publish.extend(other.host_publish)
        self.expose_ports.extend(other.expose_ports)
