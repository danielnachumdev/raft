"""Resolve the effective ordered firewall document for render."""

from pathlib import Path

from raft.core.core.models.firewall import FirewallDocument
from raft.core.core.models.state.firewall_store import FirewallStore


class FirewallEffective:
    """Durable firewall document, or empty when none has been saved yet."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._store = FirewallStore(root)
        self._document = self._resolve()

    @property
    def document(self) -> FirewallDocument:
        return self._document

    @property
    def adopted(self) -> bool:
        """True when a durable firewall file exists."""
        return self._store.exists()

    def is_active(self) -> bool:
        return self._document.is_active()

    def has_service_rules(self, service: str) -> bool:
        target = service.strip().lower()
        return any(
            rule.service.strip().lower() == target for rule in self._document.rules
        )

    def _resolve(self) -> FirewallDocument:
        loaded = self._store.load()
        if loaded is not None:
            return loaded
        return FirewallDocument()
