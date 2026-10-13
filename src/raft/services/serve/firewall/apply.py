"""Persist ordered firewall rules then render + reload gate nginx."""

from typing import Any, Dict, Mapping, Optional

from raft.core.core.models.firewall import FirewallDocument
from raft.core.core.models.stack import Stack
from raft.core.lifecycle.deploy.orchestrator import Orchestrator
from raft.core.lifecycle.render.firewall import FirewallEffective
from raft.services.serve.acl.eligibility import AclEligibility
from .store_write import FirewallDocumentWriter


class ServeFirewallService:
    """Durable firewall CRUD + import/export + gate nginx apply."""

    def __init__(
        self,
        stack: Stack,
        *,
        orchestrator: Optional[Orchestrator] = None,
    ) -> None:
        self._stack = stack
        self._orch = orchestrator or Orchestrator(stack)
        self._writer = FirewallDocumentWriter(stack.root)
        self._eligibility = AclEligibility(stack)

    def get(self) -> Dict[str, Any]:
        return FirewallEffective(self._stack.root).document.to_public()

    def put(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        result = self._writer.put(body)
        self._apply()
        return {**result, "applied": True}

    def clear(self) -> Dict[str, Any]:
        result = self._writer.clear()
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
                apps.append({"name": app.name, "publicHost": meta.get("publicHost")})
        return {"services": [{"name": "any", "label": "Any (edge-wide)"}, *apps]}

    def _apply(self) -> None:
        self._orch.render()
