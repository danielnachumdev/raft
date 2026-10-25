"""Build baseline firewall recommendations for new operators."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.models.firewall import (
    ANY_CIDR,
    PORT_ANY,
    SERVICE_ANY,
    FirewallDocument,
    FirewallRule,
)
from raft.core.core.models.state.recommendation_dismissals import (
    FirewallDismissalStore,
)
from raft.core.lifecycle.render.firewall import FirewallEffective


class FirewallRecommendations:
    """Per-port permit + default-deny suggestions with dismiss persistence."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._dismissals = FirewallDismissalStore(root)

    def list_public(self) -> Dict[str, Any]:
        document = FirewallEffective(self._root).document
        dismissed = self._dismissals.list_ids()
        items = [
            item
            for item in self._candidates(document)
            if item["id"] not in dismissed
        ]
        return {"recommendations": items}

    def dismiss(self, recommendation_id: str) -> Dict[str, Any]:
        self._dismissals.dismiss(recommendation_id)
        return self.list_public()

    def _candidates(self, document: FirewallDocument) -> List[Dict[str, Any]]:
        items = self._permit_candidates(document)
        deny = self._default_deny_candidate(document)
        if deny is not None:
            items.append(deny)
        return items

    def _permit_candidates(
        self, document: FirewallDocument
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for port in self._edge_ports():
            if self._has_permit_for_port(document, port):
                continue
            items.append(self._permit_item(port))
        return items

    def _default_deny_candidate(
        self, document: FirewallDocument
    ) -> Optional[Dict[str, Any]]:
        if self._has_default_deny(document):
            return None
        rule = self._default_deny_rule()
        return {
            "id": "default-deny",
            "kind": "default-deny",
            "title": "Default deny (any → deny)",
            "summary": (
                f"Deny {ANY_CIDR} / any port / any protocol / any service "
                f"(place last; first-match baseline)."
            ),
            "rule": rule.to_public(),
            "append": True,
        }

    def _permit_item(self, port: int) -> Dict[str, Any]:
        rule = self._permit_rule(port)
        return {
            "id": f"permit-port-{port}",
            "kind": "permit-port",
            "title": f"Permit edge port {port}",
            "summary": (
                f"Allow {ANY_CIDR} on port {port}/tcp for service any "
                f"(published HTTP edge listen)."
            ),
            "rule": rule.to_public(),
        }

    def _edge_ports(self) -> Tuple[int, ...]:
        edge = SettingsLoader().load(self._root).edge
        ports: List[int] = []
        if edge.http is not None:
            ports.append(edge.http)
        if edge.https is not None:
            ports.append(edge.https)
        return tuple(ports) if ports else (80,)

    @staticmethod
    def _permit_rule(port: int) -> FirewallRule:
        return FirewallRule(
            id=f"permit-port-{port}",
            cidr=ANY_CIDR,
            port=port,
            protocol="tcp",
            service=SERVICE_ANY,
            action="permit",
        )

    @staticmethod
    def _default_deny_rule() -> FirewallRule:
        return FirewallRule(
            id="default-deny",
            cidr=ANY_CIDR,
            port=PORT_ANY,
            protocol="any",
            service=SERVICE_ANY,
            action="deny",
        )

    @staticmethod
    def _has_permit_for_port(document: FirewallDocument, port: int) -> bool:
        return any(
            rule.action == "permit" and rule.applies_to_port(port)
            for rule in document.rules
        )

    @staticmethod
    def _has_default_deny(document: FirewallDocument) -> bool:
        return any(
            rule.action in {"deny", "drop"}
            and rule.is_port_any()
            and rule.service.strip().lower() in {"", SERVICE_ANY}
            and rule.cidr in {ANY_CIDR, "0.0.0.0/0", "::/0"}
            for rule in document.rules
        )
