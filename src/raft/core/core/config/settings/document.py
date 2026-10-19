"""Serialize :class:`RaftConfig` to/from the settings.yaml JSON shape."""

from typing import Any, Mapping

from .alerts_config import AlertsConfig
from .dashboard_config import DashboardAuthConfig, DashboardConfig, DashboardOAuthConfig
from .types import (
    AcmeConfig,
    AclConfig,
    EdgeConfig,
    EdgeStream,
    GateAclConfig,
    GithubServeConfig,
    HealingConfig,
    LoggingConfig,
    MetricsConfig,
    NotificationChannelConfig,
    NotificationsConfig,
    RaftConfig,
    ServiceLogsConfig,
)


class SettingsDocument:
    """CamelCase document codec matching ``examples/settings.yaml`` keys."""

    def to_raw(self, cfg: RaftConfig) -> dict[str, Any]:
        return {
            "logging": self._logging(cfg.logging),
            "edge": self._edge(cfg.edge),
            "healing": self._healing(cfg.healing),
            "metrics": self._metrics(cfg.metrics),
            "serviceLogs": self._service_logs(cfg.service_logs),
            "acme": self._acme(cfg.acme),
            "github": self._github(cfg.github),
            "notifications": self._notifications(cfg.notifications),
            "acl": self._acl(cfg.acl),
            "alerts": self._alerts(cfg.alerts),
            "dashboard": self._dashboard(cfg.dashboard),
        }

    def _logging(self, cfg: LoggingConfig) -> dict[str, Any]:
        return {
            "dir": cfg.dir,
            "file": cfg.file,
            "level": cfg.level,
            "retentionMaxAgeDays": cfg.retention_max_age_days,
            "retentionMaxBytes": cfg.retention_max_bytes,
        }

    def _edge(self, cfg: EdgeConfig) -> dict[str, Any]:
        return {
            "http": cfg.http,
            "https": cfg.https,
            "streams": [self._stream(s) for s in cfg.streams],
        }

    @staticmethod
    def _stream(stream: EdgeStream) -> dict[str, Any]:
        return {
            "name": stream.name,
            "port": stream.port,
            "protocol": stream.protocol,
        }

    def _healing(self, cfg: HealingConfig) -> dict[str, Any]:
        return {
            "enabled": cfg.enabled,
            "intervalSeconds": cfg.interval_seconds,
            "timeoutSeconds": cfg.timeout_seconds,
            "failThreshold": cfg.fail_threshold,
            "cooldownSeconds": cfg.cooldown_seconds,
            "maxRestarts": cfg.max_restarts,
            "escalateAfterRestarts": cfg.escalate_after_restarts,
        }

    def _metrics(self, cfg: MetricsConfig) -> dict[str, Any]:
        return {
            "intervalSeconds": cfg.interval_seconds,
            "timeoutSeconds": cfg.timeout_seconds,
            "batchSize": cfg.batch_size,
            "flushSeconds": cfg.flush_seconds,
            "retentionMaxAgeDays": cfg.retention_max_age_days,
            "retentionMaxBytes": cfg.retention_max_bytes,
        }

    def _service_logs(self, cfg: ServiceLogsConfig) -> dict[str, Any]:
        return {
            "enabled": cfg.enabled,
            "intervalSeconds": cfg.interval_seconds,
            "timeoutSeconds": cfg.timeout_seconds,
            "retentionMaxAgeDays": cfg.retention_max_age_days,
            "retentionMaxBytes": cfg.retention_max_bytes,
            "includeEdge": cfg.include_edge,
        }

    def _acme(self, cfg: AcmeConfig) -> dict[str, Any]:
        return {
            "email": cfg.email,
            "directory": cfg.directory,
            "renewDaysBeforeExpiry": cfg.renew_days_before_expiry,
            "challenge": cfg.challenge,
        }

    def _github(self, cfg: GithubServeConfig) -> dict[str, Any]:
        return {
            "clientId": cfg.client_id,
            "clientSecret": cfg.client_secret,
            "sessionTtlSeconds": cfg.session_ttl_seconds,
        }

    def _notifications(self, cfg: NotificationsConfig) -> dict[str, Any]:
        return {
            "enabled": cfg.enabled,
            "channels": [self._channel(ch) for ch in cfg.channels],
        }

    @staticmethod
    def _channel(channel: NotificationChannelConfig) -> dict[str, Any]:
        return {
            "id": channel.id,
            "type": channel.type,
            "enabled": channel.enabled,
            "settings": dict(channel.settings),
        }

    def _acl(self, cfg: AclConfig) -> dict[str, Any]:
        return {"gate": self._gate(cfg.gate)}

    @staticmethod
    def _gate(gate: GateAclConfig) -> dict[str, Any]:
        return gate.to_policy().to_public()

    @staticmethod
    def _alerts(cfg: AlertsConfig) -> dict[str, Any]:
        return {
            "enabled": cfg.enabled,
            "intervalSeconds": cfg.interval_seconds,
            "timeoutSeconds": cfg.timeout_seconds,
        }

    def _dashboard(self, cfg: DashboardConfig) -> dict[str, Any]:
        return {
            "enabled": cfg.enabled,
            "port": cfg.port,
            "publicHost": cfg.public_host,
            "tls": cfg.tls,
            "auth": self._dashboard_auth(cfg.auth),
        }

    def _dashboard_auth(self, auth: DashboardAuthConfig) -> dict[str, Any]:
        return {
            "mode": auth.mode,
            "passwordHash": auth.password_hash,
            "verifyUrl": auth.verify_url,
            "signInUrl": auth.sign_in_url,
            "identityHeader": auth.identity_header,
            "oauth": self._dashboard_oauth(auth.oauth),
        }

    @staticmethod
    def _dashboard_oauth(oauth: DashboardOAuthConfig) -> dict[str, Any]:
        return {
            "provider": oauth.provider,
            "redirectPath": oauth.redirect_path,
            "allowlistFile": oauth.allowlist_file,
            "issuerUrl": oauth.issuer_url,
        }

    @staticmethod
    def require_mapping(raw: Any, *, path: str) -> Mapping[str, Any]:
        if not isinstance(raw, Mapping):
            from raft.core.core.errors.cta import OperatorError

            raise OperatorError(
                f"{path} must be a JSON object.\n"
                f"Fix: PUT a full settings document with section keys",
                has_fix=False,
            )
        return raw
