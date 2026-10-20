"""Load operator settings — ``~/.raft/settings.yaml`` (not service inventory)."""

from pathlib import Path
from typing import Any, Optional

import yaml

from raft.core.core.errors.cta import OperatorError
from ..paths.home import RaftHome
from .strategies import (
    AcmeSettingsParser,
    AlertsSettingsParser,
    DashboardSettingsParser,
    EdgeSettingsParser,
    GithubSettingsParser,
    HealingSettingsParser,
    LoggingSettingsParser,
    MetricsSettingsParser,
    NotificationsSettingsParser,
    ServiceLogsSettingsParser,
)
from .types import RaftConfig


class SettingsLoader:
    """Parse ``settings.yaml`` into :class:`RaftConfig`."""

    def __init__(self) -> None:
        self._logging = LoggingSettingsParser()
        self._edge = EdgeSettingsParser()
        self._healing = HealingSettingsParser()
        self._metrics = MetricsSettingsParser()
        self._service_logs = ServiceLogsSettingsParser()
        self._acme = AcmeSettingsParser()
        self._github = GithubSettingsParser()
        self._notifications = NotificationsSettingsParser()
        self._alerts = AlertsSettingsParser()
        self._dashboard = DashboardSettingsParser()

    def load(self, data_home: Path, *, path: Optional[Path] = None) -> RaftConfig:
        config_path = path or RaftHome().settings_path(data_home)
        if not config_path.exists():
            return self.from_raw(None)
        return self.from_raw(self._read_mapping(config_path))

    def from_raw(self, data: Optional[dict[str, Any]]) -> RaftConfig:
        """Parse an in-memory settings mapping (same rules as the file)."""
        return self._from_raw(data)

    def _from_raw(self, data: Optional[dict[str, Any]]) -> RaftConfig:
        if data is None:
            return self._defaults()
        return RaftConfig(
            logging=self._logging.parse(data.get("logging") or {}),
            edge=self._edge.parse(data.get("edge")),
            healing=self._healing.parse(data.get("healing")),
            metrics=self._metrics.parse(data.get("metrics")),
            service_logs=self._service_logs.parse(data.get("serviceLogs")),
            acme=self._acme.parse(data.get("acme")),
            github=self._github.parse(data.get("github")),
            notifications=self._notifications.parse(data.get("notifications")),
            alerts=self._alerts.parse(data.get("alerts")),
            dashboard=self._dashboard.parse(data.get("dashboard")),
        )

    def _defaults(self) -> RaftConfig:
        return RaftConfig(
            github=self._github.parse(None),
            notifications=self._notifications.parse(None),
            alerts=self._alerts.parse(None),
            dashboard=self._dashboard.parse(None),
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


def load_config(data_home: Path, *, path: Optional[Path] = None) -> RaftConfig:
    return SettingsLoader().load(data_home, path=path)
