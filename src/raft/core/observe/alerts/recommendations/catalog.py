"""Default alert-setup recommendation templates (generic rule payloads)."""

from typing import Any, Dict, List, Mapping, Sequence

from .defaults import default_specs


class AlertRecommendationCatalog:
    """Built-in setup suggestions expressed as normal alert rule documents."""

    @classmethod
    def candidates(cls) -> List[Dict[str, Any]]:
        return [cls._from_spec(spec) for spec in default_specs()]

    @classmethod
    def _from_spec(cls, spec: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "id": spec["id"],
            "kind": spec["kind"],
            "title": spec["title"],
            "summary": spec["summary"],
            "rule": cls._rule_from_spec(spec),
        }

    @staticmethod
    def _rule_from_spec(spec: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "id": spec["rule_id"],
            "name": spec["name"],
            "enabled": True,
            "severity": spec["severity"],
            "description": spec["description"],
            "for": spec["for"],
            "cooldown": "15m",
            "repeatEvery": "0s",
            "notifyOnRecovery": True,
            "noData": "ok",
            "channelIds": [],
            "condition": {
                "signal": spec["signal"],
                "select": dict(spec["select"]),
                "kind": spec["kind_id"],
                "params": dict(spec["params"]),
            },
        }

    @staticmethod
    def covers(
        existing: Sequence[Mapping[str, Any]], candidate: Mapping[str, Any]
    ) -> bool:
        """True when an existing rule already satisfies the recommendation."""
        rule = candidate.get("rule") or {}
        want_id = str(rule.get("id") or candidate.get("id") or "")
        want_cond = rule.get("condition") if isinstance(rule, Mapping) else None
        for item in existing:
            if AlertRecommendationCatalog._covers_one(item, want_id, want_cond):
                return True
        return False

    @staticmethod
    def _covers_one(item: Any, want_id: str, want_cond: Any) -> bool:
        if not isinstance(item, Mapping):
            return False
        if want_id and str(item.get("id") or "") == want_id:
            return True
        return bool(
            want_cond
            and AlertRecommendationCatalog._same_leaf(item.get("condition"), want_cond)
        )

    @staticmethod
    def _same_leaf(left: Any, right: Any) -> bool:
        if not isinstance(left, Mapping) or not isinstance(right, Mapping):
            return False
        if left.get("signal") != right.get("signal"):
            return False
        if left.get("kind") != right.get("kind"):
            return False
        if dict(left.get("select") or {}) != dict(right.get("select") or {}):
            return False
        return AlertRecommendationCatalog._params_cover(
            left.get("params") or {}, right.get("params") or {}
        )

    @staticmethod
    def _params_cover(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
        for key, want in right.items():
            got = left.get(key)
            if isinstance(want, list) and isinstance(got, list):
                if set(str(x) for x in want) - set(str(x) for x in got):
                    return False
            elif got != want:
                return False
        return True
