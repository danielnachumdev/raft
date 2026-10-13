"""Serializable ordered firewall document (persist / import / export)."""

from dataclasses import dataclass
from typing import Any, Mapping

from raft.core.core.errors.cta import OperatorError
from .rule import FirewallRule

FIREWALL_DOCUMENT_VERSION = 1


@dataclass(frozen=True)
class FirewallDocument:
    """Canonical rule list; JSON/YAML round-trip is lossless for these fields."""

    rules: tuple[FirewallRule, ...] = ()
    version: int = FIREWALL_DOCUMENT_VERSION
    source: str = "firewall"

    def is_active(self) -> bool:
        return bool(self.rules)

    def to_public(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "source": self.source,
            "rules": [rule.to_public() for rule in self.rules],
        }

    def to_export(self) -> dict[str, Any]:
        """Lossless export body (no runtime ``source`` hint)."""
        return {
            "version": self.version,
            "rules": [rule.to_public() for rule in self.rules],
        }

    @classmethod
    def from_mapping(cls, raw: Any, *, path: str, source: str = "firewall") -> "FirewallDocument":
        if raw is None:
            return cls(source=source)
        if not isinstance(raw, Mapping):
            raise OperatorError(
                f"{path} must be a mapping.\n"
                f"Fix: use {{version: 1, rules: [...]}}",
                has_fix=False,
            )
        version = cls._parse_version(raw.get("version"), path=f"{path}.version")
        rules = cls._parse_rules(raw.get("rules"), path=f"{path}.rules")
        return cls(rules=rules, version=version, source=source)

    @staticmethod
    def _parse_version(raw: Any, *, path: str) -> int:
        if raw is None:
            return FIREWALL_DOCUMENT_VERSION
        try:
            version = int(raw)
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                f"{path} must be an integer (got {raw!r}).\n"
                f"Fix: set version: {FIREWALL_DOCUMENT_VERSION}",
                has_fix=False,
            ) from exc
        if version != FIREWALL_DOCUMENT_VERSION:
            raise OperatorError(
                f"{path} unsupported firewall version {version}.\n"
                f"Fix: use version: {FIREWALL_DOCUMENT_VERSION}",
                has_fix=False,
            )
        return version

    @classmethod
    def _parse_rules(cls, raw: Any, *, path: str) -> tuple[FirewallRule, ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise OperatorError(
                f"{path} must be a list.\n"
                f"Fix: set rules: [{{id, cidr, port, protocol, service, action}}]",
                has_fix=False,
            )
        rules = [
            FirewallRule.from_mapping(item, path=f"{path}[{index}]")
            for index, item in enumerate(raw)
        ]
        cls._assert_unique_ids(rules, path=path)
        return tuple(rules)

    @staticmethod
    def _assert_unique_ids(rules: list[FirewallRule], *, path: str) -> None:
        seen: set[str] = set()
        for rule in rules:
            if rule.id in seen:
                raise OperatorError(
                    f"{path} duplicate id {rule.id!r}.\n"
                    f"Fix: give each firewall rule a unique id",
                    has_fix=False,
                )
            seen.add(rule.id)
