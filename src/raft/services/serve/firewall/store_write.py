"""Persist ordered firewall document under flock."""

from pathlib import Path
from typing import Any, Dict, Mapping

from raft.core.core.models.firewall import FirewallDocument
from raft.core.core.models.state.firewall_store import FirewallStore
from raft.core.platform.locking import AclLock


class FirewallDocumentWriter:
    """Validate + write ``state/firewall/rules.yaml`` under ``acl.lock``."""

    def __init__(self, data_home: Path) -> None:
        self._home = data_home
        self._store = FirewallStore(data_home)

    def put(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        with AclLock(self._home):
            document = FirewallDocument.from_mapping(
                body, path="firewall", source="firewall"
            )
            self._store.save(document)
            return document.to_public()

    def clear(self) -> Dict[str, Any]:
        return self.put({"version": 1, "rules": []})

    def adopted(self) -> bool:
        return self._store.exists()
