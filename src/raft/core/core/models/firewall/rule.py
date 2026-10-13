"""One ordered edge-firewall rule (CIDR × port × protocol × service × action)."""

from dataclasses import dataclass
from typing import Any, Mapping

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.acl_policy import AclCidr

FIREWALL_ACTIONS = frozenset({"deny", "permit", "drop"})
HTTP_EDGE_PROTOCOLS = frozenset({"", "any", "tcp", "http", "https"})
SERVICE_ANY = "any"


@dataclass(frozen=True)
class FirewallRule:
    """Durable firewall row; table order is evaluation order."""

    id: str
    cidr: str
    port: int
    protocol: str
    service: str
    action: str

    def to_public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "cidr": self.cidr,
            "port": self.port,
            "protocol": self.protocol,
            "service": self.service,
            "action": self.action,
        }

    def matches_http_edge(self) -> bool:
        return self.protocol.strip().lower() in HTTP_EDGE_PROTOCOLS

    def applies_to_service(self, service: str) -> bool:
        target = self.service.strip().lower()
        if target in {"", SERVICE_ANY}:
            return True
        return target == service.strip().lower()

    def applies_to_port(self, port: int) -> bool:
        return self.port == port

    @classmethod
    def from_mapping(cls, raw: Any, *, path: str) -> "FirewallRule":
        if not isinstance(raw, Mapping):
            raise OperatorError(
                f"{path} must be a mapping.\n"
                f"Fix: use {{id, cidr, port, protocol, service, action}}",
                has_fix=False,
            )
        return cls(
            id=cls._parse_id(raw.get("id"), path=f"{path}.id"),
            cidr=AclCidr.validate(raw.get("cidr"), path=f"{path}.cidr"),
            port=cls._parse_port(raw.get("port"), path=f"{path}.port"),
            protocol=cls._parse_protocol(raw.get("protocol"), path=f"{path}.protocol"),
            service=cls._parse_service(raw.get("service"), path=f"{path}.service"),
            action=cls._parse_action(raw.get("action"), path=f"{path}.action"),
        )

    @staticmethod
    def _parse_id(raw: Any, *, path: str) -> str:
        text = str(raw or "").strip()
        if not text:
            raise OperatorError(
                f"{path} is required.\nFix: set a unique id (e.g. office-443)",
                has_fix=False,
            )
        return text

    @staticmethod
    def _parse_port(raw: Any, *, path: str) -> int:
        try:
            port = int(raw)
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                f"{path} must be an integer port (1-65535).\n"
                f"Fix: set port: 443",
                has_fix=False,
            ) from exc
        if port < 1 or port > 65535:
            raise OperatorError(
                f"{path} must be between 1 and 65535 (got {port}).\n"
                f"Fix: set a valid TCP/UDP port",
                has_fix=False,
            )
        return port

    @staticmethod
    def _parse_protocol(raw: Any, *, path: str) -> str:
        text = str(raw if raw is not None else "tcp").strip().lower()
        if not text:
            raise OperatorError(
                f"{path} is required.\nFix: set protocol (e.g. tcp) or other",
                has_fix=False,
            )
        return text

    @staticmethod
    def _parse_service(raw: Any, *, path: str) -> str:
        text = str(raw if raw is not None else SERVICE_ANY).strip()
        if not text:
            raise OperatorError(
                f"{path} is required.\nFix: set service: any or an App name",
                has_fix=False,
            )
        return text

    @staticmethod
    def _parse_action(raw: Any, *, path: str) -> str:
        action = str(raw or "").strip().lower()
        if action not in FIREWALL_ACTIONS:
            raise OperatorError(
                f"{path} must be deny, permit, or drop (got {action!r}).\n"
                f"Fix: set action: deny | permit | drop",
                has_fix=False,
            )
        return action
