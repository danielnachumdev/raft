"""Describe settings.yaml section enablement for the serve Settings UI."""

from typing import Any, Dict, List

from .types import RaftConfig

_SECTION_ORDER = (
    "logging",
    "edge",
    "healing",
    "metrics",
    "serviceLogs",
    "acme",
    "github",
    "notifications",
    "alerts",
    "dashboard",
)


class SettingsSectionMeta:
    """Map RaftConfig sections to enabled/disabled UI status (no fake flags)."""

    def for_config(self, cfg: RaftConfig) -> List[Dict[str, Any]]:
        by_key = {row["key"]: row for row in self._all_rows(cfg)}
        return [by_key[key] for key in _SECTION_ORDER]

    def _all_rows(self, cfg: RaftConfig) -> List[Dict[str, Any]]:
        return [
            *self._always_blocks(),
            *self._flag_blocks(cfg),
            *self._derived_blocks(cfg),
        ]

    def _always_blocks(self) -> List[Dict[str, Any]]:
        return [
            self._always("logging", "Logging"),
            self._always("edge", "Edge"),
            self._always("metrics", "Metrics"),
        ]

    def _flag_blocks(self, cfg: RaftConfig) -> List[Dict[str, Any]]:
        return [
            self._flag("healing", "Healing", cfg.healing.enabled, "healing.enabled"),
            self._flag(
                "serviceLogs", "Service logs", cfg.service_logs.enabled,
                "serviceLogs.enabled",
            ),
            self._flag(
                "notifications", "Notifications", cfg.notifications.enabled,
                "notifications.enabled",
            ),
            self._flag("alerts", "Alerts", cfg.alerts.enabled, "alerts.enabled"),
            self._flag(
                "dashboard", "Dashboard", cfg.dashboard.enabled, "dashboard.enabled",
            ),
        ]

    def _derived_blocks(self, cfg: RaftConfig) -> List[Dict[str, Any]]:
        return [
            self._derived("acme", "ACME", bool(cfg.acme.email), "acme.email is set"),
            self._derived(
                "github",
                "GitHub",
                bool(cfg.github.client_id),
                "github.clientId is set",
            ),
        ]

    @staticmethod
    def _always(key: str, title: str) -> Dict[str, Any]:
        return {
            "key": key,
            "title": title,
            "kind": "always",
            "enabled": True,
            "source": "always present in RaftConfig",
        }

    @staticmethod
    def _flag(key: str, title: str, enabled: bool, source: str) -> Dict[str, Any]:
        return {
            "key": key,
            "title": title,
            "kind": "flag",
            "enabled": enabled,
            "source": source,
        }

    @staticmethod
    def _derived(key: str, title: str, enabled: bool, source: str) -> Dict[str, Any]:
        return {
            "key": key,
            "title": title,
            "kind": "derived",
            "enabled": enabled,
            "source": source,
        }
