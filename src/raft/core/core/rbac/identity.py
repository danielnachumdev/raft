"""Resolve the RBAC subject from dashboard auth mode + request."""

from typing import Mapping, Optional

from raft.core.core.config.settings.dashboard_config import DashboardConfig
from raft.core.core.rbac.subject import RbacSubject

# Password mode until per-user accounts land: single implicit subject.
PASSWORD_BOOTSTRAP_SUBJECT = "admin"
NONE_BOOTSTRAP_SUBJECT = "local"


class RbacIdentity:
    """Map admission mode → normalized subject string."""

    def __init__(self, config: DashboardConfig) -> None:
        self._cfg = config

    def from_headers(
        self,
        headers: Mapping[str, str],
        *,
        password_username: Optional[str] = None,
    ) -> str:
        mode = self._cfg.auth.mode
        if mode in {"oauth", "external"}:
            return self._from_identity_header(headers)
        if mode == "password":
            raw = password_username or PASSWORD_BOOTSTRAP_SUBJECT
            return RbacSubject.normalize(raw)
        return NONE_BOOTSTRAP_SUBJECT

    def _from_identity_header(self, headers: Mapping[str, str]) -> str:
        header = self._cfg.auth.identity_header
        # Starlette headers are case-insensitive; Mapping may be plain dict.
        value = ""
        for key, item in headers.items():
            if key.lower() == header.lower():
                value = item
                break
        return RbacSubject.normalize(value)
