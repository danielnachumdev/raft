"""Operator-facing warnings when settings changes need follow-up commands."""

from typing import Any, List, Optional

from .types import EdgeConfig, RaftConfig


class SettingsSideEffects:
    """Describe host actions required after a settings document change."""

    GATE_RECREATE = (
        "Published edge ports (http / https / streams) changed. "
        "Run `raft redeploy gate` so the gate container publishes the new "
        "listeners (reload alone is not enough; brief edge downtime)."
    )
    GITHUB_ENV = (
        "GitHub OAuth env vars (RAFT_GITHUB_*) override settings.yaml when set."
    )
    CONTROLLER_PICKUP = (
        "healing / metrics / serviceLogs / alerts cadence changes apply on "
        "the next controller job tick (no stack recreate)."
    )
    DASHBOARD_ENABLE = (
        "dashboard.enabled is now true. Run `raft render`, then "
        "`raft up dashboard` (or `raft redeploy dashboard`) to bring up "
        "raft-dashboard. Saving settings alone does not start the container."
    )
    DASHBOARD_DISABLE = (
        "dashboard.enabled is now false. Run `raft render` so Compose omits "
        "raft-dashboard; bring a leftover container down with "
        "`raft down dashboard` if needed."
    )

    def for_replace(
        self, *, before: RaftConfig, after: RaftConfig
    ) -> List[dict[str, Any]]:
        notes: List[dict[str, Any]] = []
        if self._edge_ports_changed(before.edge, after.edge):
            notes.append(self._note("edge.ports", self.GATE_RECREATE, severity="warn"))
        dash = self._dashboard_enabled_note(before, after)
        if dash is not None:
            notes.append(dash)
        notes.append(
            self._note("controller", self.CONTROLLER_PICKUP, severity="info")
        )
        return notes

    def for_get(self, cfg: RaftConfig) -> List[dict[str, Any]]:
        del cfg
        return [self._note("github.env", self.GITHUB_ENV, severity="info")]

    def _dashboard_enabled_note(
        self, before: RaftConfig, after: RaftConfig
    ) -> Optional[dict[str, Any]]:
        if before.dashboard.enabled == after.dashboard.enabled:
            return None
        if after.dashboard.enabled:
            return self._note("dashboard.enabled", self.DASHBOARD_ENABLE, severity="info")
        return self._note("dashboard.enabled", self.DASHBOARD_DISABLE, severity="info")

    @staticmethod
    def _edge_ports_changed(before: EdgeConfig, after: EdgeConfig) -> bool:
        return before.published_ports() != after.published_ports()

    @staticmethod
    def _note(code: str, message: str, *, severity: str) -> dict[str, Any]:
        return {"code": code, "severity": severity, "message": message}
