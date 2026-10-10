from __future__ import annotations

"""Controller job implementations (heal, metrics, acme, scale)."""

from typing import Any

from ...utils.package_exports import PackageExports

__all__ = [
    "ACME_INTERVAL_SECONDS",
    "ACME_TIMEOUT_SECONDS",
    "AcmeJobSync",
    "ControllerJob",
    "HTTP_METRICS_FILENAME",
    "HealJob",
    "Healer",
    "HttpMetricsRecorder",
    "METRICS_DIR",
    "METRICS_FILENAME",
    "MetricsJob",
    "MetricsRecorder",
    "ScaleJob",
    "Scaler",
    "WAKE_HTTP_PORT",
    "needs_heal",
    "run_heal_forever",
]

_EXPORTS = PackageExports(
    __name__,
    {
        "ACME_INTERVAL_SECONDS": ".acme:ACME_INTERVAL_SECONDS",
        "ACME_TIMEOUT_SECONDS": ".acme:ACME_TIMEOUT_SECONDS",
        "AcmeJobSync": ".acme:AcmeJobSync",
        "ControllerJob": ".controller_job:ControllerJob",
        "HTTP_METRICS_FILENAME": ".metrics:HTTP_METRICS_FILENAME",
        "HealJob": ".heal:HealJob",
        "Healer": ".heal:Healer",
        "HttpMetricsRecorder": ".metrics:HttpMetricsRecorder",
        "METRICS_DIR": ".metrics:METRICS_DIR",
        "METRICS_FILENAME": ".metrics:METRICS_FILENAME",
        "MetricsJob": ".metrics:MetricsJob",
        "MetricsRecorder": ".metrics:MetricsRecorder",
        "ScaleJob": ".scale:ScaleJob",
        "Scaler": ".scale:Scaler",
        "WAKE_HTTP_PORT": ".scale:WAKE_HTTP_PORT",
        "needs_heal": ".heal:needs_heal",
        "run_heal_forever": ".heal:run_heal_forever",
    },
)


def __getattr__(name: str) -> Any:
    value = _EXPORTS.get(name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
