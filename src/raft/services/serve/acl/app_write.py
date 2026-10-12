"""Persist per-app ACL under ``state/acl/apps/``."""

from pathlib import Path
from typing import Any, Dict, Mapping

from raft.core.core.models.acl_policy import AclPolicy
from raft.core.core.models.state.acl_store import AppAclStore
from raft.core.platform.locking import AclLock
from .eligibility import AclEligibility


class AppAclWriter:
    """Validate eligibility, then write durable per-app ACL JSON."""

    def __init__(self, data_home: Path, eligibility: AclEligibility) -> None:
        self._home = data_home
        self._store = AppAclStore(data_home)
        self._eligibility = eligibility

    def get_public(self, name: str) -> Dict[str, Any]:
        app, _ = self._eligibility.require_app(name)
        return self._store.load(app.name).to_public()

    def put(self, name: str, body: Mapping[str, Any]) -> Dict[str, Any]:
        app, _ = self._eligibility.require_app(name)
        with AclLock(self._home):
            policy = AclPolicy.from_mapping(body, path=f"acl.apps.{app.name}")
            self._store.save(app.name, policy)
            return policy.to_public()

    def clear(self, name: str) -> Dict[str, Any]:
        app, _ = self._eligibility.require_app(name)
        with AclLock(self._home):
            self._store.delete(app.name)
            return AclPolicy().to_public()
