"""Write ordered-firewall include lines for a gate server listen port."""

from pathlib import Path

from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.models.app import App
from raft.core.lifecycle.render.acl import AclEffective, AclIncWriter
from .effective import FirewallEffective
from .inc_writer import FirewallIncWriter


class PolicyIncludes:
    """Always compile firewall fragments; clear leftover ACL includes."""

    def __init__(self, root: Path, edge: EdgeConfig, gate_http_dir: Path) -> None:
        self._fw = FirewallEffective(root)
        ports = self._listen_ports(edge)
        self._fw_writer = FirewallIncWriter(gate_http_dir, self._fw, ports=ports)
        self._acl_writer = AclIncWriter(gate_http_dir, AclEffective(root))

    def write_all(self, apps: list[App]) -> None:
        self._fw_writer.write_all(apps)
        self._acl_writer.clear_all()

    def gate_include(self, port: int) -> str:
        return self._fw_writer.gate_include(port)

    def host_include(self, name: str, port: int) -> str:
        return self._fw_writer.host_include(name, port)

    def needs_host_gate_server(self, name: str) -> bool:
        return self._fw.has_service_rules(name)

    @staticmethod
    def _listen_ports(edge: EdgeConfig) -> tuple[int, ...]:
        ports: list[int] = []
        if edge.http is not None:
            ports.append(edge.http)
        if edge.https is not None:
            ports.append(edge.https)
        return tuple(ports) if ports else (80,)
