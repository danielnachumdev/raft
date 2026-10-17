"""Parse ``alerts:`` from settings.yaml."""

from typing import Any

from raft.core.core.errors.cta import OperatorError

from ..alerts_config import (
    DEFAULT_ALERTS_ENABLED,
    DEFAULT_ALERTS_INTERVAL_SECONDS,
    DEFAULT_ALERTS_TIMEOUT_SECONDS,
    MIN_ALERTS_INTERVAL_SECONDS,
    AlertsConfig,
)
from ..scalars import SettingsScalars
from ..section import SettingsSectionParser


class AlertsSettingsParser(SettingsSectionParser[AlertsConfig]):
    """Validate and build :class:`AlertsConfig`."""

    def __init__(self) -> None:
        self._scalars = SettingsScalars()

    def parse(self, raw: Any) -> AlertsConfig:
        if raw is None:
            return AlertsConfig()
        if not isinstance(raw, dict):
            raise self._not_mapping()
        enabled = bool(raw.get("enabled", DEFAULT_ALERTS_ENABLED))
        interval = self._interval(raw)
        timeout = self._scalars.pos_float(
            raw, "timeoutSeconds", DEFAULT_ALERTS_TIMEOUT_SECONDS, "alerts"
        )
        return AlertsConfig(
            enabled=enabled,
            interval_seconds=interval,
            timeout_seconds=timeout,
        )

    def _interval(self, raw: dict) -> float:
        interval = self._scalars.pos_float(
            raw, "intervalSeconds", DEFAULT_ALERTS_INTERVAL_SECONDS, "alerts"
        )
        if interval < MIN_ALERTS_INTERVAL_SECONDS:
            raise OperatorError(
                f"settings.yaml alerts.intervalSeconds must be ≥ "
                f"{MIN_ALERTS_INTERVAL_SECONDS:g}.\n"
                f"Fix: set intervalSeconds: 60"
            )
        return interval

    @staticmethod
    def _not_mapping() -> OperatorError:
        return OperatorError(
            "settings.yaml alerts must be a mapping.\n"
            "Fix: set alerts: {enabled: true, intervalSeconds: 60}"
        )
