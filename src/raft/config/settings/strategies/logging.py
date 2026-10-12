"""Parse ``logging:`` from settings.yaml."""

from typing import Any

from ....errors.cta import OperatorError
from ...paths.constants import LOGS_DIRNAME
from ..scalars import SettingsScalars
from ..section import SettingsSectionParser
from ..types import (
    DEFAULT_LOGGING_RETENTION_MAX_AGE_DAYS,
    DEFAULT_LOGGING_RETENTION_MAX_BYTES,
    LoggingConfig,
)


class LoggingSettingsParser(SettingsSectionParser[LoggingConfig]):
    """Validate and build :class:`LoggingConfig`."""

    def __init__(self) -> None:
        self._scalars = SettingsScalars()

    def parse(self, raw: Any) -> LoggingConfig:
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml logging must be a mapping.\n"
                "Fix: set logging: {level: INFO, ...} in ~/.raft/settings.yaml"
            )
        level = str(raw.get("level", "INFO")).strip().upper() or "INFO"
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in allowed:
            raise OperatorError(
                f"settings.yaml logging.level must be one of {sorted(allowed)}, "
                f"got {level!r}.\n"
                f"Fix: set logging.level in ~/.raft/settings.yaml"
            )
        return LoggingConfig(
            dir=str(raw.get("dir", LOGS_DIRNAME)).strip() or LOGS_DIRNAME,
            file=str(raw.get("file", "raft.log")).strip() or "raft.log",
            level=level,
            retention_max_age_days=self._scalars.pos_int(
                raw,
                "retentionMaxAgeDays",
                DEFAULT_LOGGING_RETENTION_MAX_AGE_DAYS,
                "logging",
            ),
            retention_max_bytes=self._scalars.pos_int(
                raw,
                "retentionMaxBytes",
                DEFAULT_LOGGING_RETENTION_MAX_BYTES,
                "logging",
            ),
        )
