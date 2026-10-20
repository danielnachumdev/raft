"""Import firewall rules + dismissed recommendations from disk."""

from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from raft.core.core.db.models.firewall import FirewallDismissedRow, FirewallRuleRow
from raft.core.core.models.state.firewall_dismissals import FirewallDismissalStore
from raft.core.core.models.state.firewall_store import FirewallStore


class FirewallFileImporter:
    """Copy ``host/firewall/`` YAML/JSON into normalized tables."""

    def __init__(self, home: Path) -> None:
        self._store = FirewallStore(home)
        self._dismissals = FirewallDismissalStore(home)

    def import_into(self, session: Session) -> int:
        rules = self._import_rules(session)
        self._import_dismissals(session)
        return rules

    def _import_rules(self, session: Session) -> int:
        document = self._store.load()
        session.execute(delete(FirewallRuleRow))
        if document is None:
            return 0
        for position, rule in enumerate(document.rules):
            session.add(
                FirewallRuleRow(
                    id=rule.id,
                    position=position,
                    cidr=rule.cidr,
                    port=rule.port,
                    protocol=rule.protocol,
                    service=rule.service,
                    action=rule.action,
                    document_version=document.version,
                )
            )
        return len(document.rules)

    def _import_dismissals(self, session: Session) -> None:
        session.execute(delete(FirewallDismissedRow))
        for recommendation_id in sorted(self._dismissals.list_ids()):
            session.add(FirewallDismissedRow(recommendation_id=recommendation_id))
