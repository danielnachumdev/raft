"""Build and merge ordered firewall rules from HTTP request inspection (#198)."""

import re
from typing import Any, Mapping, Optional

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.acl_policy import AclCidr
from raft.core.core.models.firewall import (
    FIREWALL_DOCUMENT_VERSION,
    PORT_ANY,
    FirewallDocument,
    FirewallRule,
)
from raft.core.core.models.stack import Stack
from raft.core.lifecycle.render.firewall import FirewallEffective
from .eligibility import FirewallEligibility

_ID_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


class InspectionFirewall:
    """Prefill + ordered merge for client-IP rules from request inspection.

    New and updated rules are **prepended** (index 0) so they evaluate before
    broad ``permit any`` / default-deny rows. Operators can expand the host
    CIDR in the draft before apply.
    """

    def __init__(self, stack: Stack) -> None:
        self._stack = stack
        self._eligibility = FirewallEligibility(stack)

    def draft(
        self,
        *,
        client_ip: str,
        service: str = "",
        action: str = "deny",
    ) -> dict[str, Any]:
        cidr = self.host_cidr(client_ip)
        rule = self._draft_rule(cidr=cidr, service=service, action=action)
        matches = self.matching_rules(
            FirewallEffective(self._stack.root).document, cidr
        )
        return {
            "cidr": cidr,
            "rule": rule.to_public(),
            "matches": [item.to_public() for item in matches],
            "insert": "prepend",
        }

    def _draft_rule(
        self, *, cidr: str, service: str, action: str
    ) -> FirewallRule:
        app_name = self._resolve_service(service)
        port = self._preferred_edge_port()
        return FirewallRule.from_mapping(
            {
                "id": self.rule_id(cidr=cidr, service=app_name),
                "cidr": cidr,
                "port": "any" if port == PORT_ANY else port,
                "protocol": "tcp",
                "service": app_name,
                "action": action,
            },
            path="firewall.rule",
        )

    def apply_rule(self, body: Mapping[str, Any]) -> FirewallDocument:
        rule = FirewallRule.from_mapping(body, path="firewall.rule")
        document = FirewallEffective(self._stack.root).document
        return self.prepend(document, rule)

    def remove_for_client(
        self,
        *,
        client_ip: str,
        rule_id: str = "",
    ) -> FirewallDocument:
        cidr = self.host_cidr(client_ip)
        document = FirewallEffective(self._stack.root).document
        next_doc = self.without_matching(document, cidr=cidr, rule_id=rule_id)
        if len(next_doc.rules) == len(document.rules):
            raise OperatorError(
                f"No firewall rule matches client {client_ip!r} "
                f"(host CIDR {cidr}).\n"
                f"Fix: add a rule from inspection first, or remove it under "
                f"Settings → Firewall",
                has_fix=False,
            )
        return next_doc

    @staticmethod
    def host_cidr(client_ip: str) -> str:
        return AclCidr.validate(client_ip, path="firewall.client_ip")

    @staticmethod
    def rule_id(*, cidr: str, service: str) -> str:
        host = cidr.split("/", 1)[0].replace(":", "-").replace(".", "-")
        svc = _ID_SAFE.sub("-", service.strip() or "any").strip("-") or "any"
        return f"inspect-{svc}-{host}"[:120]

    @staticmethod
    def matching_rules(
        document: FirewallDocument, cidr: str
    ) -> list[FirewallRule]:
        target = cidr.strip().lower()
        return [rule for rule in document.rules if rule.cidr.lower() == target]

    @staticmethod
    def prepend(
        document: FirewallDocument, rule: FirewallRule
    ) -> FirewallDocument:
        others = [item for item in document.rules if item.id != rule.id]
        return FirewallDocument(
            rules=(rule, *others),
            version=document.version or FIREWALL_DOCUMENT_VERSION,
            source="firewall",
        )

    @staticmethod
    def without_matching(
        document: FirewallDocument,
        *,
        cidr: str,
        rule_id: str = "",
    ) -> FirewallDocument:
        wanted_id = rule_id.strip()
        target = cidr.strip().lower()
        kept: list[FirewallRule] = []
        for rule in document.rules:
            if wanted_id:
                drop = rule.id == wanted_id
            else:
                drop = rule.cidr.lower() == target
            if not drop:
                kept.append(rule)
        return FirewallDocument(
            rules=tuple(kept),
            version=document.version or FIREWALL_DOCUMENT_VERSION,
            source="firewall",
        )

    def _resolve_service(self, service: str) -> str:
        text = service.strip()
        if not text or text.lower() == "any":
            return "any"
        app_name = self._find_app_name(text)
        if app_name is None or not self._eligibility.meta(app_name).get(
            "supported"
        ):
            raise OperatorError(
                f"firewall.service {text!r} is not an applied Host-routed "
                f"App.\n"
                f"Fix: use service: any or an expose: http App with "
                f"publicHost",
                has_fix=False,
            )
        return app_name

    def _find_app_name(self, name: str) -> Optional[str]:
        if name == "raft-dashboard":
            meta = self._eligibility.meta("raft-dashboard")
            return "raft-dashboard" if meta.get("supported") else None
        for app in self._stack.apps:
            if app.name == name or app.compose_id == name:
                return app.name
        return None

    def _preferred_edge_port(self) -> int:
        edge = SettingsLoader().load(self._stack.root).edge
        if edge.https is not None:
            return edge.https
        if edge.http is not None:
            return edge.http
        return PORT_ANY
