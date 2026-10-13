"""Persist ACL then render + reload gate nginx (reload-class, not recreate)."""

from typing import Any, Dict, Mapping, Optional

from raft.core.core.models.stack import Stack
from raft.core.lifecycle.deploy.orchestrator import Orchestrator
from .app_write import AppAclWriter
from .eligibility import AclEligibility
from .settings_write import GateAclSettingsWriter


class ServeAclService:
    """Durable ACL CRUD + gate nginx apply for ``raft serve``."""

    def __init__(
        self,
        stack: Stack,
        *,
        orchestrator: Optional[Orchestrator] = None,
    ) -> None:
        self._stack = stack
        self._orch = orchestrator or Orchestrator(stack)
        self._eligibility = AclEligibility(stack)
        self._gate = GateAclSettingsWriter(stack.root)
        self._apps = AppAclWriter(stack.root, self._eligibility)

    def gate_get(self) -> Dict[str, Any]:
        return self._gate.get_public()

    def gate_put(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        result = self._gate.put(body)
        self._apply()
        return {**result, "applied": True}

    def gate_clear(self) -> Dict[str, Any]:
        result = self._gate.clear()
        self._apply()
        return {**result, "applied": True}

    def app_meta(self, name: str) -> Dict[str, Any]:
        return self._eligibility.meta(name)

    def app_get(self, name: str) -> Dict[str, Any]:
        return self._apps.get_public(name)

    def app_put(self, name: str, body: Mapping[str, Any]) -> Dict[str, Any]:
        result = self._apps.put(name, body)
        self._apply()
        return {**result, "applied": True}

    def app_clear(self, name: str) -> Dict[str, Any]:
        result = self._apps.clear(name)
        self._apply()
        return {**result, "applied": True}

    def _apply(self) -> None:
        self._orch.render()
