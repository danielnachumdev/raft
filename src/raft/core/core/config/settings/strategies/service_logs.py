"""Parse ``serviceLogs:`` from settings.yaml."""

from typing import Any

from raft.core.core.errors.cta import OperatorError
from ..scalars import SettingsScalars
from ..section import SettingsSectionParser
from ..types import (
    DEFAULT_SERVICE_LOGS_INTERVAL_SECONDS,
    DEFAULT_SERVICE_LOGS_RETENTION_MAX_AGE_DAYS,
    DEFAULT_SERVICE_LOGS_RETENTION_MAX_BYTES,
    DEFAULT_SERVICE_LOGS_TIMEOUT_SECONDS,
    ServiceLogsConfig,
)


class ServiceLogsSettingsParser(SettingsSectionParser[ServiceLogsConfig]):
    """Validate and build :class:`ServiceLogsConfig`."""

    def __init__(self) -> None:
        self._scalars = SettingsScalars()

    def parse(self, raw: Any) -> ServiceLogsConfig:
        if raw is None:
            return ServiceLogsConfig()
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml serviceLogs must be a mapping.\n"
                "Fix: set serviceLogs: {enabled: true, ...} in ~/.raft/settings.yaml"
            )
        return ServiceLogsConfig(
            enabled=bool(raw.get("enabled", True)),
            include_edge=bool(raw.get("includeEdge", True)),
            **self._timing_fields(raw),
            **self._retention_fields(raw),
        )

    def _timing_fields(self, raw: dict) -> dict:
        s = self._scalars
        return {
            "interval_seconds": s.pos_float(
                raw,
                "intervalSeconds",
                DEFAULT_SERVICE_LOGS_INTERVAL_SECONDS,
                "serviceLogs",
            ),
            "timeout_seconds": s.pos_float(
                raw,
                "timeoutSeconds",
                DEFAULT_SERVICE_LOGS_TIMEOUT_SECONDS,
                "serviceLogs",
            ),
        }

    def _retention_fields(self, raw: dict) -> dict:
        s = self._scalars
        return {
            "retention_max_age_days": s.pos_int(
                raw,
                "retentionMaxAgeDays",
                DEFAULT_SERVICE_LOGS_RETENTION_MAX_AGE_DAYS,
                "serviceLogs",
            ),
            "retention_max_bytes": s.pos_int(
                raw,
                "retentionMaxBytes",
                DEFAULT_SERVICE_LOGS_RETENTION_MAX_BYTES,
                "serviceLogs",
            ),
        }
