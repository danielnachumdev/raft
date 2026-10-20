"""Parse ``healing:`` from settings.yaml."""

from typing import Any

from raft.core.core.errors.cta import OperatorError
from ..scalars import SettingsScalars
from ..section import SettingsSectionParser
from ..types import (
    DEFAULT_HEAL_INTERVAL_SECONDS,
    DEFAULT_HEAL_TIMEOUT_SECONDS,
    HealingConfig,
)


class HealingSettingsParser(SettingsSectionParser[HealingConfig]):
    """Validate and build :class:`HealingConfig`."""

    def __init__(self) -> None:
        self._scalars = SettingsScalars()

    def parse(self, raw: Any) -> HealingConfig:
        if raw is None:
            return HealingConfig()
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml healing must be a mapping.\n"
                "Fix: set healing: {enabled: true, ...} in ~/.raft/host/settings.yaml"
            )
        return self._from_mapping(raw)

    def _from_mapping(self, raw: dict) -> HealingConfig:
        s = self._scalars
        return HealingConfig(
            enabled=bool(raw.get("enabled", False)),
            interval_seconds=s.pos_float(
                raw, "intervalSeconds", DEFAULT_HEAL_INTERVAL_SECONDS, "healing"
            ),
            timeout_seconds=s.pos_float(
                raw, "timeoutSeconds", DEFAULT_HEAL_TIMEOUT_SECONDS, "healing"
            ),
            fail_threshold=s.pos_int(raw, "failThreshold", 3, "healing"),
            cooldown_seconds=s.pos_float(raw, "cooldownSeconds", 60.0, "healing"),
            max_restarts=s.pos_int(raw, "maxRestarts", 1, "healing"),
            escalate_after_restarts=s.pos_int(raw, "escalateAfterRestarts", 1, "healing"),
        )
