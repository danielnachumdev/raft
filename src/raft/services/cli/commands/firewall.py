"""Fire component: ``raft firewall …`` (ordered edge firewall)."""

from typing import Any, Mapping, Optional

from raft.core.core.models.stack import Stack
from raft.core.lifecycle.firewall import FirewallService

from ..utils.deps import Orchestrator
from .firewall_io import FirewallCliIo
from .firewall_output import FirewallCliOutput


class FirewallCLI:
    """Manage ordered gate firewall rules under ``state/firewall/rules.yaml``.

    Same validation and ``acl.lock`` as Settings → Firewall Save: persist →
    render → gate nginx **reload** (never recreate for rule-only edits).
    """

    def __init__(
        self,
        stack: Stack,
        *,
        orchestrator: Optional[Orchestrator] = None,
        service: Optional[FirewallService] = None,
    ) -> None:
        self._stack = stack
        self._out = FirewallCliOutput()
        self._io = FirewallCliIo()
        self._service = service or FirewallService(
            stack, orchestrator=orchestrator or Orchestrator(stack)
        )

    def show(self, json: bool = False) -> None:
        """Show the effective ordered firewall document."""
        payload = self._service.get()
        if json:
            self._out.say_json(payload)
            return
        self._out.rules_table(list(payload.get("rules") or []))

    def replace(self, file: str) -> None:
        """Replace rules from a YAML/JSON file and apply (reload gate nginx).

        Example::

            raft firewall replace --file rules.yaml
        """
        path = self._io.require_file(file, command="replace")
        result = self._service.put(self._io.read_mapping(path))
        self._out.applied(result)

    def export(self, file: Optional[str] = None, json: bool = False) -> None:
        """Export the serializable firewall document (no ``source`` field)."""
        payload = self._service.export_document()
        text = self._io.dump(payload, as_json=json)
        if file:
            self._out.write_file(file, text)
            return
        self._out.say(text.rstrip())

    def import_document(self, file: str) -> None:
        """Validate + import a document (YAML/JSON), then apply.

        Example::

            raft firewall import_document --file rules.json
        """
        path = self._io.require_file(file, command="import_document")
        result = self._service.import_document(self._io.read_mapping(path))
        self._out.applied(result, note="Imported and applied firewall document.")

    def services(self, json: bool = False) -> None:
        """List ``any`` plus Host-routed Apps eligible for service-scoped rules."""
        payload = self._service.services()
        if json:
            self._out.say_json(payload)
            return
        self._out.services_table(list(payload.get("services") or []))

    def recommendations(self, json: bool = False) -> None:
        """List open baseline recommendations (per-port permit + default deny)."""
        payload = self._service.recommendations()
        if json:
            self._out.say_json(payload)
            return
        self._out.recommendations_table(list(payload.get("recommendations") or []))

    def dismiss(self, recommendation_id: str) -> None:
        """Dismiss a recommendation id (e.g. ``permit-port-80``)."""
        payload = self._service.dismiss_recommendation(recommendation_id)
        self._out.say(f"Dismissed {recommendation_id}.")
        remaining = payload.get("recommendations") or []
        self._out.say(f"{len(remaining)} recommendation(s) still open.")

    def draft(
        self,
        client_ip: str,
        service: str = "",
        action: str = "deny",
        json: bool = False,
    ) -> None:
        """Prefill a from-inspection rule for a client IP (does not apply).

        Example::

            raft firewall draft --client-ip=192.0.2.1 --service=demo-api
        """
        payload = self._service.inspection_draft(
            client_ip=client_ip, service=service, action=action
        )
        self._out.emit(payload, as_json=json)

    def apply_inspection(
        self,
        client_ip: str,
        service: str = "",
        action: str = "deny",
        file: Optional[str] = None,
    ) -> None:
        """Draft (or load ``--file`` rule) and prepend + apply from inspection.

        Example::

            raft firewall apply_inspection --client-ip=192.0.2.1 --service=demo-api
        """
        rule = self._inspection_rule(
            client_ip=client_ip, service=service, action=action, file=file
        )
        result = self._service.apply_from_inspection({"rule": rule})
        self._out.applied(
            result,
            note=f"Prepended rule {rule.get('id')!r} and applied.",
        )

    def remove_inspection(
        self, client_ip: str, rule_id: str = ""
    ) -> None:
        """Remove rules matching the client host CIDR (optional ``--rule-id``).

        Example::

            raft firewall remove_inspection --client-ip=192.0.2.1
        """
        result = self._service.remove_from_inspection(
            {"client_ip": client_ip, "rule_id": rule_id}
        )
        self._out.applied(
            result,
            note=f"Removed inspection rule(s) for {client_ip!r} and applied.",
        )

    def _inspection_rule(
        self,
        *,
        client_ip: str,
        service: str,
        action: str,
        file: Optional[str],
    ) -> Mapping[str, Any]:
        if file:
            return self._rule_from_file(file)
        draft = self._service.inspection_draft(
            client_ip=client_ip, service=service, action=action
        )
        return draft["rule"]

    def _rule_from_file(self, file: str) -> Mapping[str, Any]:
        raw = self._io.read_mapping(file)
        if "rule" in raw and isinstance(raw["rule"], dict):
            return raw["rule"]
        return raw
