"""Derive oauth allowlist from RBAC admitted subjects (single SoT)."""

from pathlib import Path

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.rbac.admission import RbacAdmission
from raft.core.core.rbac.document import RbacDocument
from raft.core.core.rbac.store import RbacStore

from .oauth_allowlist import DashboardOAuthAllowlist


class RbacAllowlistSync:
    """When auth.mode is oauth and rbac.yaml exists, rewrite the allowlist file."""

    def __init__(self, home: Path) -> None:
        self._home = home
        self._store = RbacStore(home)
        self._allow = DashboardOAuthAllowlist(home)

    def sync(self, document: RbacDocument | None = None) -> dict[str, object]:
        cfg = SettingsLoader().load(self._home).dashboard
        if cfg.auth.mode != "oauth":
            return {"synced": False, "reason": "auth.mode is not oauth"}
        if not self._store.exists() and document is None:
            return {"synced": False, "reason": "rbac.yaml missing (bootstrap)"}
        doc = document
        if doc is None:
            doc = self._store.load() or RbacDocument.empty()
        lines = RbacAdmission.lines_for_allowlist(doc)
        written = self._allow.write(
            lines, relative=cfg.auth.oauth.allowlist_file
        )
        return {"synced": True, **written}
