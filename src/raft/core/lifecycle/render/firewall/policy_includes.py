"""Choose ACL vs ordered-firewall include lines for a gate server listen port."""

from pathlib import Path

from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.models.app import App
from raft.core.lifecycle.render.acl import AclEffective, AclIncWriter
from .effective import FirewallEffective
from .inc_writer import FirewallIncWriter


class PolicyIncludes:
    """Write ACL or firewall fragments; resolve include text per listen port."""

    def __init__(self, root: Path, edge: EdgeConfig, gate_http_dir: Path) -> None:
        self._edge = edge
        self._acl = AclEffective(root)
        self._fw = FirewallEffective(root)
        self._acl_writer = AclIncWriter(gate_http_dir, self._acl)
        ports = self._listen_ports()
        self._fw_writer = FirewallIncWriter(gate_http_dir, self._fw, ports=ports)
        self._adopted = self._fw.adopted

    def write_all(self, apps: list[App]) -> None:
        if self._adopted:
            self._fw_writer.write_all(apps)
            self._acl_writer.clear_all()
            return
        self._acl_writer.write_all(apps)
        self._fw_writer.clear_all()

    def gate_include(self, port: int) -> str:
        if self._adopted:
            return self._fw_writer.gate_include(port)
        return self._acl_writer.gate_include()

    def host_include(self, name: str, port: int) -> str:
        if self._adopted:
            return self._fw_writer.host_include(name, port)
        return self._acl_writer.host_include(name)

    def needs_host_gate_server(self, name: str) -> bool:
        if self._adopted:
            return self._fw.has_service_rules(name)
        return self._acl.needs_host_gate_server(name)

    def _listen_ports(self) -> tuple[int, ...]:
        ports: list[int] = []
        if self._edge.http is not None:
            ports.append(self._edge.http)
        if self._edge.https is not None:
            ports.append(self._edge.https)
        return tuple(ports) if ports else (80,)
