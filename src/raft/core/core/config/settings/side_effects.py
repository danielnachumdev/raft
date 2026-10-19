"""Operator-facing warnings when settings changes need follow-up commands."""

from typing import Any, List

from .types import EdgeConfig, RaftConfig


class SettingsSideEffects:
    """Describe host actions required after a settings document change."""

    GATE_RECREATE = (
        "Published edge ports (http / https / streams) changed. "
        "Run `raft gate recreate` so the gate container publishes the new "
        "listeners (reload alone is not enough)."
    )
    ACL_LEGACY = (
        "acl.gate is legacy leftover from flat IP ACL. Prefer ordered "
        "firewall rules under Settings → Firewall; leftover ACL migrates "
        "into the firewall editor until Save."
    )
    GITHUB_ENV = (
        "GitHub OAuth env vars (RAFT_GITHUB_*) override settings.yaml when set."
    )
    CONTROLLER_PICKUP = (
        "healing / metrics / serviceLogs / alerts cadence changes apply on "
        "the next controller job tick (no stack recreate)."
    )

    def for_replace(
        self, *, before: RaftConfig, after: RaftConfig
    ) -> List[dict[str, Any]]:
        notes: List[dict[str, Any]] = []
        if self._edge_ports_changed(before.edge, after.edge):
            notes.append(self._note("edge.ports", self.GATE_RECREATE, severity="warn"))
        if after.acl.gate.is_active():
            notes.append(self._note("acl.gate", self.ACL_LEGACY, severity="info"))
        notes.append(
            self._note("controller", self.CONTROLLER_PICKUP, severity="info")
        )
        return notes

    def for_get(self, cfg: RaftConfig) -> List[dict[str, Any]]:
        notes: List[dict[str, Any]] = []
        if cfg.acl.gate.is_active():
            notes.append(self._note("acl.gate", self.ACL_LEGACY, severity="info"))
        notes.append(self._note("github.env", self.GITHUB_ENV, severity="info"))
        return notes

    @staticmethod
    def _edge_ports_changed(before: EdgeConfig, after: EdgeConfig) -> bool:
        return before.published_ports() != after.published_ports()

    @staticmethod
    def _note(code: str, message: str, *, severity: str) -> dict[str, Any]:
        return {"code": code, "severity": severity, "message": message}
