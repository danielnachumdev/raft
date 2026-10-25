"""Parse ``metrics:`` from settings.yaml."""

from typing import Any

from raft.core.core.errors.cta import OperatorError
from ..scalars import SettingsScalars
from ..section import SettingsSectionParser
from ..types import (
    DEFAULT_METRICS_BATCH_SIZE,
    DEFAULT_METRICS_FLUSH_SECONDS,
    DEFAULT_METRICS_INTERVAL_SECONDS,
    DEFAULT_METRICS_PRESSURE_THRESHOLD,
    DEFAULT_METRICS_RETENTION_MAX_AGE_DAYS,
    DEFAULT_METRICS_RETENTION_MAX_BYTES,
    DEFAULT_METRICS_TIMEOUT_SECONDS,
    MetricsConfig,
)


class MetricsSettingsParser(SettingsSectionParser[MetricsConfig]):
    """Validate and build :class:`MetricsConfig`."""

    def __init__(self) -> None:
        self._scalars = SettingsScalars()

    def parse(self, raw: Any) -> MetricsConfig:
        if raw is None:
            return MetricsConfig()
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml metrics must be a mapping.\n"
                "Fix: set metrics: {intervalSeconds: 60, ...} in ~/.raft/host/settings.yaml"
            )
        return MetricsConfig(
            **self._timing_fields(raw),
            **self._retention_fields(raw),
            pressure_threshold=self._scalars.unit_float(
                raw,
                "pressureThreshold",
                DEFAULT_METRICS_PRESSURE_THRESHOLD,
                "metrics",
            ),
        )

    def _timing_fields(self, raw: dict) -> dict:
        s = self._scalars
        return {
            "interval_seconds": s.pos_float(
                raw, "intervalSeconds", DEFAULT_METRICS_INTERVAL_SECONDS, "metrics"
            ),
            "timeout_seconds": s.pos_float(
                raw, "timeoutSeconds", DEFAULT_METRICS_TIMEOUT_SECONDS, "metrics"
            ),
            "batch_size": s.pos_int(raw, "batchSize", DEFAULT_METRICS_BATCH_SIZE, "metrics"),
            "flush_seconds": s.pos_float(
                raw, "flushSeconds", DEFAULT_METRICS_FLUSH_SECONDS, "metrics"
            ),
        }

    def _retention_fields(self, raw: dict) -> dict:
        s = self._scalars
        return {
            "retention_max_age_days": s.pos_int(
                raw,
                "retentionMaxAgeDays",
                DEFAULT_METRICS_RETENTION_MAX_AGE_DAYS,
                "metrics",
            ),
            "retention_max_bytes": s.pos_int(
                raw,
                "retentionMaxBytes",
                DEFAULT_METRICS_RETENTION_MAX_BYTES,
                "metrics",
            ),
        }
