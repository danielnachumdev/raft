"""Load operator settings — ``~/.raft/settings.yaml`` (not service inventory)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

from raft.errors import OperatorError

from .paths import LOGS_DIRNAME, settings_path
from .settings_edge import EdgeSettingsParser
from .settings_types import (
    HealingConfig,
    LoggingConfig,
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
        )

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
            interval_seconds=self._pos_float(raw, "intervalSeconds", 15.0),
            fail_threshold=self._pos_int(raw, "failThreshold", 3),
            cooldown_seconds=self._pos_float(raw, "cooldownSeconds", 60.0),
            max_restarts=self._pos_int(raw, "maxRestarts", 1),
            escalate_after_restarts=self._pos_int(raw, "escalateAfterRestarts", 1),
        )

    @staticmethod
    def _pos_float(raw: dict, key: str, default: float) -> float:
        if key not in raw or raw[key] is None:
            return default
        try:
            value = float(raw[key])
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                f"settings.yaml healing.{key} must be a number, got {raw[key]!r}.\n"
                f"Fix: set healing.{key} in ~/.raft/settings.yaml"
            ) from exc
        if value <= 0:
            raise OperatorError(
                f"settings.yaml healing.{key} must be > 0, got {value}.\n"
                f"Fix: set healing.{key} to a positive number in ~/.raft/settings.yaml"
            )
        return value

    @staticmethod
    def _pos_int(raw: dict, key: str, default: int) -> int:
        if key not in raw or raw[key] is None:
            return default
        try:
            value = int(raw[key])
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                f"settings.yaml healing.{key} must be an integer, got {raw[key]!r}.\n"
                f"Fix: set healing.{key} in ~/.raft/settings.yaml"
            ) from exc
        if value < 1:
            raise OperatorError(
                f"settings.yaml healing.{key} must be >= 1, got {value}.\n"
                f"Fix: set healing.{key} to a positive integer in ~/.raft/settings.yaml"
            )
        return value


def load_config(data_home: Path, *, path: Optional[Path] = None) -> RaftConfig:
    return SettingsLoader().load(data_home, path=path)
