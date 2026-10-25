"""Parse ``serviceLogs:`` from settings.yaml."""

from typing import Any

from raft.core.core.errors.cta import OperatorError
from ..scalars import SettingsScalars
from ..section import SettingsSectionParser
from ..types import (
    DEFAULT_SERVICE_LOGS_FETCH_TIMEOUT_SECONDS,
    DEFAULT_SERVICE_LOGS_INTERVAL_SECONDS,
    DEFAULT_SERVICE_LOGS_MAX_FETCH_BYTES,
    DEFAULT_SERVICE_LOGS_MAX_FETCH_LINES,
    DEFAULT_SERVICE_LOGS_MAX_SERVICES_PER_TICK,
    DEFAULT_SERVICE_LOGS_RETENTION_MAX_AGE_DAYS,
    DEFAULT_SERVICE_LOGS_RETENTION_MAX_BYTES,
    DEFAULT_SERVICE_LOGS_TIMEOUT_SECONDS,
    ServiceLogsConfig,
)

_SECTION = "serviceLogs"


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
                "Fix: set serviceLogs: {enabled: true, ...} in ~/.raft/host/settings.yaml"
            )
        return ServiceLogsConfig(
            enabled=bool(raw.get("enabled", True)),
            include_edge=bool(raw.get("includeEdge", True)),
            **self._timing_fields(raw),
            **self._retention_fields(raw),
            **self._budget_fields(raw),
        )

    def _timing_fields(self, raw: dict) -> dict:
        return self._floats(
            raw,
            (
                ("interval_seconds", "intervalSeconds", DEFAULT_SERVICE_LOGS_INTERVAL_SECONDS),
                ("timeout_seconds", "timeoutSeconds", DEFAULT_SERVICE_LOGS_TIMEOUT_SECONDS),
                (
                    "fetch_timeout_seconds",
                    "fetchTimeoutSeconds",
                    DEFAULT_SERVICE_LOGS_FETCH_TIMEOUT_SECONDS,
                ),
            ),
        )

    def _retention_fields(self, raw: dict) -> dict:
        return self._ints(
            raw,
            (
                (
                    "retention_max_age_days",
                    "retentionMaxAgeDays",
                    DEFAULT_SERVICE_LOGS_RETENTION_MAX_AGE_DAYS,
                ),
                (
                    "retention_max_bytes",
                    "retentionMaxBytes",
                    DEFAULT_SERVICE_LOGS_RETENTION_MAX_BYTES,
                ),
            ),
        )

    def _budget_fields(self, raw: dict) -> dict:
        return self._ints(
            raw,
            (
                ("max_fetch_bytes", "maxFetchBytes", DEFAULT_SERVICE_LOGS_MAX_FETCH_BYTES),
                ("max_fetch_lines", "maxFetchLines", DEFAULT_SERVICE_LOGS_MAX_FETCH_LINES),
                (
                    "max_services_per_tick",
                    "maxServicesPerTick",
                    DEFAULT_SERVICE_LOGS_MAX_SERVICES_PER_TICK,
                ),
            ),
        )

    def _floats(self, raw: dict, specs: tuple) -> dict:
        return {
            dest: self._scalars.pos_float(raw, key, default, _SECTION)
            for dest, key, default in specs
        }

    def _ints(self, raw: dict, specs: tuple) -> dict:
        return {
            dest: self._scalars.pos_int(raw, key, default, _SECTION)
            for dest, key, default in specs
        }
