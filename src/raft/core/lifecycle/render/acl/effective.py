"""Resolve which ACL policy applies to gate default vs Host servers."""

from pathlib import Path

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.models.acl_policy import AclPolicy
from raft.core.core.models.state.acl_store import AppAclStore


class AclEffective:
    """Gate settings + per-app store → effective policies for render."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._store = AppAclStore(root)
        self._gate = SettingsLoader().load(root).acl.gate.to_policy()

    @property
    def gate(self) -> AclPolicy:
        return self._gate

    def for_app(self, name: str) -> AclPolicy:
        return self._store.load(name)

    def host_policy(self, name: str) -> AclPolicy:
        """App ACL wins when active; otherwise inherit gate."""
        app = self.for_app(name)
        if app.is_active():
            return app
        return self._gate

    def needs_host_gate_server(self, name: str) -> bool:
        """Plain HTTP apps need a Host gate server when app ACL is active."""
        return self.for_app(name).is_active()
