"""Alert instance fingerprints and rule hashes."""

import hashlib
import json
from typing import Any

from ..model.rule import AlertRule


class AlertFingerprint:
    """Stable fingerprint and condition hash helpers."""

    @staticmethod
    def of(rule_id: str, subject: str) -> str:
        return f"{rule_id}|{subject}"

    @staticmethod
    def rule_hash(rule: AlertRule) -> str:
        payload = {
            "condition": rule.condition.to_export(),
            "for": rule.for_seconds,
            "noData": rule.no_data,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"
