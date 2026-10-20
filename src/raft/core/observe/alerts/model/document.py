"""Versioned alert rules document."""

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from raft.core.core.errors.cta import OperatorError

from ..constants import DOCUMENT_VERSION, MAX_RULES
from ..registries import AlertRegistries
from .rule import AlertRule
from .rule_parser import AlertRuleParser


@dataclass(frozen=True)
class AlertRulesDocument:
    version: int
    rules: Tuple[AlertRule, ...]

    @classmethod
    def empty(cls) -> "AlertRulesDocument":
        return cls(version=DOCUMENT_VERSION, rules=())

    @classmethod
    def from_mapping(
        cls,
        raw: Any,
        *,
        registries: AlertRegistries,
        path: str = "host/alerts/rules.yaml",
    ) -> "AlertRulesDocument":
        if raw is None:
            return cls.empty()
        rules_raw = cls._validate_header(raw, path)
        rules = cls._parse_rules(rules_raw, registries, path)
        return cls(version=DOCUMENT_VERSION, rules=tuple(rules))

    @classmethod
    def _validate_header(cls, raw: Any, path: str) -> list:
        if not isinstance(raw, Mapping):
            raise OperatorError(
                f"{path} must be a mapping.\nFix: set version: 1 and rules: []"
            )
        version = raw.get("version", DOCUMENT_VERSION)
        if version != DOCUMENT_VERSION:
            raise OperatorError(
                f"{path}: unsupported version {version!r}.\nFix: set version: 1"
            )
        rules_raw = raw.get("rules") or []
        if not isinstance(rules_raw, list):
            raise OperatorError(f"{path}.rules must be a list.\nFix: set rules: []")
        if len(rules_raw) > MAX_RULES:
            raise OperatorError(
                f"{path}.rules: more than {MAX_RULES} rules.\nFix: remove unused rules"
            )
        return rules_raw

    @classmethod
    def _parse_rules(cls, rules_raw, registries, path) -> List[AlertRule]:
        parser = AlertRuleParser(registries)
        rules: List[AlertRule] = []
        seen = set()
        for i, item in enumerate(rules_raw):
            rule = parser.parse(item, path=f"{path}.rules[{i}]")
            if rule.id in seen:
                raise OperatorError(
                    f"{path}.rules[{i}].id: duplicate id {rule.id!r}.\n"
                    f"Fix: give each rule a unique id"
                )
            seen.add(rule.id)
            rules.append(rule)
        return rules

    def to_export(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "rules": [r.to_export() for r in self.rules],
        }

    def to_public(self) -> Dict[str, Any]:
        return self.to_export()

    def get(self, rule_id: str) -> Optional[AlertRule]:
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None
