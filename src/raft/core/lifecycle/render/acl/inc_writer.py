"""Write generated ACL ``.inc`` snippets under ``gate-http/acl/``."""

from pathlib import Path

from raft.core.core.models.acl_policy import AclPolicy
from raft.core.core.models.app import App
from .effective import AclEffective
from .nginx_text import AclNginxText


class AclIncWriter:
    """Persist nginx include fragments for gate + per-app Host ACL."""

    GATE_REL = "_gate.inc"

    def __init__(self, gate_http_dir: Path, effective: AclEffective) -> None:
        self._dir = gate_http_dir / "acl"
        self._effective = effective

    def write_all(self, apps: list[App]) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        self._write(self.GATE_REL, self._effective.gate)
        keep = {self.GATE_REL}
        for app in apps:
            rel = self.app_rel(app.name)
            self._write(rel, self._effective.host_policy(app.name))
            keep.add(rel)
        self._prune(keep)

    @staticmethod
    def app_rel(name: str) -> str:
        safe = name.replace("/", "_").replace("\\", "_")
        return f"{safe}.inc"

    def gate_include(self) -> str:
        if not self._effective.gate.is_active():
            return ""
        return AclNginxText.include_line(self.GATE_REL)

    def host_include(self, app_name: str) -> str:
        if not self._effective.host_policy(app_name).is_active():
            return ""
        return AclNginxText.include_line(self.app_rel(app_name))

    def _write(self, relative: str, policy: AclPolicy) -> None:
        body = AclNginxText.location_rules(policy) if policy.is_active() else ""
        (self._dir / relative).write_text(body, encoding="utf-8")

    def _prune(self, keep: set[str]) -> None:
        for path in self._dir.glob("*.inc"):
            if path.name not in keep:
                path.unlink()
