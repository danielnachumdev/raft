"""Persist ordered firewall rules then render + reload gate nginx."""

from typing import Any, Dict, Mapping, Optional

from raft.core.core.models.firewall import FirewallDocument
from raft.core.core.models.stack import Stack
from raft.core.lifecycle.deploy.orchestrator import Orchestrator
from raft.core.lifecycle.render.firewall import FirewallEffective
from .eligibility import FirewallEligibility
from .from_inspection import InspectionFirewall
from .recommendations import FirewallRecommendations
from .store_write import FirewallDocumentWriter


class FirewallService:
    """Durable firewall CRUD + import/export + recommendations + apply."""

    def __init__(
        self,
        stack: Stack,
        *,
        orchestrator: Optional[Orchestrator] = None,
    ) -> None:
        self._stack = stack
        self._orch = orchestrator or Orchestrator(stack)
        self._writer = FirewallDocumentWriter(stack.root)
        self._eligibility = FirewallEligibility(stack)
        self._recommendations = FirewallRecommendations(stack.root)
        self._inspection = InspectionFirewall(stack)

    def get(self) -> Dict[str, Any]:
        return FirewallEffective(self._stack.root).document.to_public()

    def put(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        result = self._writer.put(body)
        self._apply()
        return {**result, "applied": True}

    def export_document(self) -> Dict[str, Any]:
        return FirewallEffective(self._stack.root).document.to_export()

    def import_document(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        document = FirewallDocument.from_mapping(
            body, path="firewall.import", source="firewall"
        )
        return self.put(document.to_export())

    def services(self) -> Dict[str, Any]:
        apps = []
        for app in self._stack.apps:
            meta = self._eligibility.meta(app.name)
            if meta.get("supported"):
                apps.append(
                    {"name": app.name, "publicHost": meta.get("publicHost")}
                )
        return {"services": [{"name": "any", "label": "Any (edge-wide)"}, *apps]}

    def recommendations(self) -> Dict[str, Any]:
        return self._recommendations.list_public()

    def dismiss_recommendation(self, recommendation_id: str) -> Dict[str, Any]:
        return self._recommendations.dismiss(recommendation_id)

    def inspection_draft(
        self, *, client_ip: str, service: str = "", action: str = "deny"
    ) -> Dict[str, Any]:
        return self._inspection.draft(
            client_ip=client_ip, service=service, action=action
        )

    def apply_from_inspection(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        document = self._inspection.apply_rule(body.get("rule") or body)
        return self.put(document.to_export())

    def remove_from_inspection(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        document = self._inspection.remove_for_client(
            client_ip=str(body.get("client_ip") or ""),
            rule_id=str(body.get("rule_id") or ""),
        )
        return self.put(document.to_export())

    def _apply(self) -> None:
        self._orch.render()
