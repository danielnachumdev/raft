"""Alerts controller settings (interval / enabled only)."""

from dataclasses import dataclass

DEFAULT_ALERTS_ENABLED = True
DEFAULT_ALERTS_INTERVAL_SECONDS = 60.0
DEFAULT_ALERTS_TIMEOUT_SECONDS = 30.0
MIN_ALERTS_INTERVAL_SECONDS = 15.0


@dataclass(frozen=True)
class AlertsConfig:
    """Controller alert evaluation schedule (rules live under host/alerts/)."""

    enabled: bool = DEFAULT_ALERTS_ENABLED
    interval_seconds: float = DEFAULT_ALERTS_INTERVAL_SECONDS
    timeout_seconds: float = DEFAULT_ALERTS_TIMEOUT_SECONDS
