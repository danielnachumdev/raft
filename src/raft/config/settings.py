"""Load operator settings — ``~/.raft/settings.yaml`` (not service inventory)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

from raft.errors import OperatorError

from .paths import LOGS_DIRNAME, settings_path
from .settings_edge import EdgeSettingsParser
from .settings_types import (
    DEFAULT_HEAL_INTERVAL_SECONDS,
    DEFAULT_HEAL_TIMEOUT_SECONDS,
    DEFAULT_LOGGING_RETENTION_MAX_AGE_DAYS,
    DEFAULT_LOGGING_RETENTION_MAX_BYTES,
    DEFAULT_METRICS_BATCH_SIZE,
    DEFAULT_METRICS_FLUSH_SECONDS,
    DEFAULT_METRICS_INTERVAL_SECONDS,
    DEFAULT_METRICS_RETENTION_MAX_AGE_DAYS,
    DEFAULT_METRICS_RETENTION_MAX_BYTES,
    DEFAULT_METRICS_TIMEOUT_SECONDS,
    HealingConfig,
    LoggingConfig,
    MetricsConfig,
    RaftConfig,
    default_config,
)


class SettingsLoader:
    """Parse ``settings.yaml`` into :class:`RaftConfig`."""

    def __init__(self) -> None:
        self._edge = EdgeSettingsParser()

    def load(self, data_home: Path, *, path: Optional[Path] = None) -> RaftConfig:
        config_path = path or settings_path(data_home)
        if not config_path.exists():
            return default_config()
        data = self._read_mapping(config_path)
        return RaftConfig(
            logging=self._parse_logging(data.get("logging") or {}),
            edge=self._edge.parse(data.get("edge")),
            healing=self._parse_healing(data.get("healing")),
            metrics=self._parse_metrics(data.get("metrics")),
        )

    def _read_mapping(self, config_path: Path) -> dict[str, Any]:
        if not config_path.is_file():
            raise OperatorError(
                f"settings path is not a file: {config_path}\n"
                f"Fix: remove the directory or point at ~/.raft/settings.yaml"
            )
        raw_text = self._read_text(config_path)
        data = self._parse_yaml(config_path, raw_text)
        if not isinstance(data, dict):
            raise OperatorError(
                f"settings.yaml must be a YAML mapping (key/value document), "
                f"got {type(data).__name__}.\n"
                f"Fix: rewrite ~/.raft/settings.yaml as `{{logging: ..., edge: ...}}`"
            )
        return data

    @staticmethod
    def _read_text(config_path: Path) -> str:
        try:
            return config_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise OperatorError(
                f"cannot read settings.yaml: {config_path}\n"
                f"Fix: ensure the file is readable — chmod u+r {config_path}"
            ) from exc

    @staticmethod
    def _parse_yaml(config_path: Path, raw_text: str) -> Any:
        try:
            return yaml.safe_load(raw_text) or {}
        except yaml.YAMLError as exc:
            raise OperatorError(
                f"invalid YAML in {config_path}: {exc}\n"
                f"Fix: repair ~/.raft/settings.yaml (logging/edge mapping)"
            ) from exc

    def _parse_logging(self, raw: Any) -> LoggingConfig:
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
            **self._logging_retention(raw),
        )

    def _logging_retention(self, raw: dict) -> dict:
        return {
            "retention_max_age_days": self._pos_int(
                raw,
                "retentionMaxAgeDays",
                DEFAULT_LOGGING_RETENTION_MAX_AGE_DAYS,
                "logging",
            ),
            "retention_max_bytes": self._pos_int(
                raw,
                "retentionMaxBytes",
                DEFAULT_LOGGING_RETENTION_MAX_BYTES,
                "logging",
            ),
        }

    def _parse_healing(self, raw: Any) -> HealingConfig:
        if raw is None:
            return HealingConfig()
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml healing must be a mapping.\n"
                "Fix: set healing: {enabled: true, ...} in ~/.raft/settings.yaml"
            )
        return HealingConfig(
            enabled=bool(raw.get("enabled", False)),
            interval_seconds=self._pos_float(
                raw, "intervalSeconds", DEFAULT_HEAL_INTERVAL_SECONDS, "healing"
            ),
            timeout_seconds=self._pos_float(
                raw, "timeoutSeconds", DEFAULT_HEAL_TIMEOUT_SECONDS, "healing"
            ),
            fail_threshold=self._pos_int(raw, "failThreshold", 3, "healing"),
            cooldown_seconds=self._pos_float(raw, "cooldownSeconds", 60.0, "healing"),
            max_restarts=self._pos_int(raw, "maxRestarts", 1, "healing"),
            escalate_after_restarts=self._pos_int(raw, "escalateAfterRestarts", 1, "healing"),
        )

    def _parse_metrics(self, raw: Any) -> MetricsConfig:
        if raw is None:
            return MetricsConfig()
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml metrics must be a mapping.\n"
                "Fix: set metrics: {intervalSeconds: 60, ...} in ~/.raft/settings.yaml"
            )
        return MetricsConfig(
            **self._metrics_schedule(raw),
            **self._metrics_retention(raw),
        )

    def _metrics_schedule(self, raw: dict) -> dict:
        return {
            "interval_seconds": self._pos_float(
                raw, "intervalSeconds", DEFAULT_METRICS_INTERVAL_SECONDS, "metrics"
            ),
            "timeout_seconds": self._pos_float(
                raw, "timeoutSeconds", DEFAULT_METRICS_TIMEOUT_SECONDS, "metrics"
            ),
            "batch_size": self._pos_int(raw, "batchSize", DEFAULT_METRICS_BATCH_SIZE, "metrics"),
            "flush_seconds": self._pos_float(
                raw, "flushSeconds", DEFAULT_METRICS_FLUSH_SECONDS, "metrics"
            ),
        }

    def _metrics_retention(self, raw: dict) -> dict:
        return {
            "retention_max_age_days": self._pos_int(
                raw,
                "retentionMaxAgeDays",
                DEFAULT_METRICS_RETENTION_MAX_AGE_DAYS,
                "metrics",
            ),
            "retention_max_bytes": self._pos_int(
                raw,
                "retentionMaxBytes",
                DEFAULT_METRICS_RETENTION_MAX_BYTES,
                "metrics",
            ),
        }

    @staticmethod
    def _pos_float(raw: dict, key: str, default: float, section: str) -> float:
        if key not in raw or raw[key] is None:
            return default
        try:
            value = float(raw[key])
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                f"settings.yaml {section}.{key} must be a number, got {raw[key]!r}.\n"
                f"Fix: set {section}.{key} in ~/.raft/settings.yaml"
            ) from exc
        if value <= 0:
            raise OperatorError(
                f"settings.yaml {section}.{key} must be > 0, got {value}.\n"
                f"Fix: set {section}.{key} to a positive number in ~/.raft/settings.yaml"
            )
        return value

    @staticmethod
    def _pos_int(raw: dict, key: str, default: int, section: str) -> int:
        if key not in raw or raw[key] is None:
            return default
        try:
            value = int(raw[key])
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                f"settings.yaml {section}.{key} must be an integer, got {raw[key]!r}.\n"
                f"Fix: set {section}.{key} in ~/.raft/settings.yaml"
            ) from exc
        if value < 1:
            raise OperatorError(
                f"settings.yaml {section}.{key} must be >= 1, got {value}.\n"
                f"Fix: set {section}.{key} to a positive integer in ~/.raft/settings.yaml"
            )
        return value


def load_config(data_home: Path, *, path: Optional[Path] = None) -> RaftConfig:
    return SettingsLoader().load(data_home, path=path)
