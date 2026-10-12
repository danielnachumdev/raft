"""Parse ``healing:`` from settings.yaml."""

from typing import Any

from ....errors.cta import OperatorError
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
                "Fix: set healing: {enabled: true, ...} in ~/.raft/settings.yaml"
            )
        return HealingConfig(
            enabled=bool(raw.get("enabled", False)),
            interval_seconds=self._scalars.pos_float(
                raw, "intervalSeconds", DEFAULT_HEAL_INTERVAL_SECONDS, "healing"
            ),
            timeout_seconds=self._scalars.pos_float(
                raw, "timeoutSeconds", DEFAULT_HEAL_TIMEOUT_SECONDS, "healing"
            ),
            fail_threshold=self._scalars.pos_int(raw, "failThreshold", 3, "healing"),
            cooldown_seconds=self._scalars.pos_float(
                raw, "cooldownSeconds", 60.0, "healing"
            ),
            max_restarts=self._scalars.pos_int(raw, "maxRestarts", 1, "healing"),
            escalate_after_restarts=self._scalars.pos_int(
                raw, "escalateAfterRestarts", 1, "healing"
            ),
        )
