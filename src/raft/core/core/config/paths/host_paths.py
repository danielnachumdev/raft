"""Resolve host/control-plane paths under ``RAFT_DATA_HOME/host/`` (#313)."""

from pathlib import Path

from .constants import (
    GATE_NGINX_FINGERPRINT,
    HOST_ACME_DIR,
    HOST_ALERTS_DIR,
    HOST_DIR,
    HOST_EDGE_SERVICE_LOGS_DIR,
    HOST_EVENTS_DIR,
    HOST_FIREWALL_DIR,
    HOST_INBOX_DIR,
    HOST_LOGS_DIR,
    HOST_METRICS_DIR,
    HOST_SECRETS_DIR,
    HOST_SERVE_DIR,
    LOCKS_DIR,
    ROUTER_NGINX_FINGERPRINT,
    SETTINGS_REL,
)


class HostPaths:
    """Control-plane durable paths for one data home."""

    def __init__(self, home: Path) -> None:
        self._home = home

    def root(self) -> Path:
        return self._home / HOST_DIR

    def settings(self) -> Path:
        return self._home / SETTINGS_REL

    def locks(self) -> Path:
        return self._home / LOCKS_DIR

    def firewall(self) -> Path:
        return self._home / HOST_FIREWALL_DIR

    def alerts(self) -> Path:
        return self._home / HOST_ALERTS_DIR

    def inbox(self) -> Path:
        return self._home / HOST_INBOX_DIR

    def events(self) -> Path:
        return self._home / HOST_EVENTS_DIR

    def metrics(self) -> Path:
        return self._home / HOST_METRICS_DIR

    def acme(self) -> Path:
        return self._home / HOST_ACME_DIR

    def serve(self) -> Path:
        return self._home / HOST_SERVE_DIR

    def secrets(self) -> Path:
        return self._home / HOST_SECRETS_DIR

    def logs(self) -> Path:
        return self._home / HOST_LOGS_DIR

    def edge_service_logs(self) -> Path:
        return self._home / HOST_EDGE_SERVICE_LOGS_DIR

    def gate_nginx_fingerprint(self) -> Path:
        return self._home / GATE_NGINX_FINGERPRINT

    def router_nginx_fingerprint(self) -> Path:
        return self._home / ROUTER_NGINX_FINGERPRINT
