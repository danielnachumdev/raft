"""Shared helpers for firewall unit tests (dummy data only)."""

from typing import Any

from raft.core.core.models.firewall import FirewallDocument, FirewallRule

_BASE = {
    "cidr": "192.0.2.0/24",
    "port": 80,
    "protocol": "tcp",
    "service": "any",
    "action": "permit",
}


def rule_dict(rule_id: str = "lab", **kwargs: Any) -> dict[str, Any]:
    body = {**_BASE, "id": rule_id}
    body.update(kwargs)
    return body


def rule(rule_id: str = "lab", **kwargs: Any) -> FirewallRule:
    return FirewallRule.from_mapping(rule_dict(rule_id, **kwargs), path="r")


def document(*rules: dict[str, Any]) -> FirewallDocument:
    return FirewallDocument.from_mapping({"version": 1, "rules": list(rules)}, path="fw")
