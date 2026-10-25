"""Positive number coercion for settings.yaml scalar fields."""

from typing import Any, Optional

from raft.core.core.errors.cta import OperatorError


class SettingsScalars:
    """Parse positive ints/floats from a settings mapping with Fix CTAs."""

    def pos_float(self, raw: dict, key: str, default: float, section: str) -> float:
        if key not in raw or raw[key] is None:
            return default
        try:
            value = float(raw[key])
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                f"settings.yaml {section}.{key} must be a number, got {raw[key]!r}.\n"
                f"Fix: set {section}.{key} in ~/.raft/host/settings.yaml"
            ) from exc
        if value <= 0:
            raise OperatorError(
                f"settings.yaml {section}.{key} must be > 0, got {value}.\n"
                f"Fix: set {section}.{key} to a positive number in ~/.raft/host/settings.yaml"
            )
        return value

    def pos_int(self, raw: dict, key: str, default: int, section: str) -> int:
        if key not in raw or raw[key] is None:
            return default
        try:
            value = int(raw[key])
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                f"settings.yaml {section}.{key} must be an integer, got {raw[key]!r}.\n"
                f"Fix: set {section}.{key} in ~/.raft/host/settings.yaml"
            ) from exc
        if value < 1:
            raise OperatorError(
                f"settings.yaml {section}.{key} must be >= 1, got {value}.\n"
                f"Fix: set {section}.{key} to a positive integer in ~/.raft/host/settings.yaml"
            )
        return value

    def optional_str(self, raw: Any) -> Optional[str]:
        if raw is None:
            return None
        text = str(raw).strip()
        return text or None
