"""Preserve masked secrets when a settings document is PUT from serve."""

from typing import Any, Mapping, Optional

from raft.core.core.errors.cta import OperatorError
from raft.core.lifecycle.dashboard.password import DashboardPassword
from raft.core.observe.notify.settings_redactor import SettingsRedactor

from .dashboard_config import DashboardAuthConfig, DashboardConfig
from .types import GithubServeConfig, NotificationChannelConfig, NotificationsConfig

class SettingsSecretsMerge:
    """Re-apply stored secrets when the client sends the redaction mask."""

    def __init__(self) -> None:
        self._redactor = SettingsRedactor()

    def notifications(
        self,
        incoming: NotificationsConfig,
        prior: NotificationsConfig,
    ) -> NotificationsConfig:
        by_id = {ch.id: ch for ch in prior.channels}
        merged = [
            self._channel(ch, by_id.get(ch.id)) for ch in incoming.channels
        ]
        return NotificationsConfig(enabled=incoming.enabled, channels=tuple(merged))

    def _channel(
        self,
        incoming: NotificationChannelConfig,
        prior: Optional[NotificationChannelConfig],
    ) -> NotificationChannelConfig:
        if prior is None:
            return incoming
        settings = self._redactor.merge_preserving_secrets(
            prior.settings, dict(incoming.settings)
        )
        return NotificationChannelConfig(
            id=incoming.id,
            type=incoming.type,
            enabled=incoming.enabled,
            settings=settings,
        )

    def github(
        self,
        incoming: GithubServeConfig,
        prior: GithubServeConfig,
    ) -> GithubServeConfig:
        secret = incoming.client_secret
        if secret == SettingsRedactor._MASK and prior.client_secret:
            secret = prior.client_secret
        return GithubServeConfig(
            client_id=incoming.client_id,
            client_secret=secret,
            session_ttl_seconds=incoming.session_ttl_seconds,
        )

    def dashboard(
        self, incoming: DashboardConfig, prior: DashboardConfig
    ) -> DashboardConfig:
        return DashboardConfig(
            enabled=incoming.enabled,
            port=incoming.port,
            public_host=incoming.public_host,
            tls=incoming.tls,
            auth=self._dashboard_auth(incoming.auth, prior.auth),
        )

    def _dashboard_auth(
        self, incoming: DashboardAuthConfig, prior: DashboardAuthConfig
    ) -> DashboardAuthConfig:
        return DashboardAuthConfig(
            mode=incoming.mode,
            password_hash=self._merge_password_hash(
                incoming.password_hash, prior.password_hash
            ),
            users=self._merge_password_users(incoming.users, prior.users),
            verify_url=incoming.verify_url,
            sign_in_url=incoming.sign_in_url,
            identity_header=incoming.identity_header,
            oauth=incoming.oauth,
        )

    def _merge_password_hash(
        self, incoming: Optional[str], prior: Optional[str]
    ) -> Optional[str]:
        if incoming == SettingsRedactor._MASK and prior:
            return prior
        return self._hash_dashboard_password(incoming)

    def _merge_password_users(self, incoming, prior):
        from raft.core.core.config.settings.dashboard_config import (
            DashboardPasswordUser,
        )

        prior_users = {u.username: u.password_hash for u in prior}
        return tuple(
            DashboardPasswordUser(
                username=user.username,
                password_hash=self._merge_password_hash(
                    user.password_hash, prior_users.get(user.username)
                )
                or user.password_hash,
            )
            for user in incoming
        )

    def _hash_dashboard_password(self, value: Optional[str]) -> Optional[str]:
        # Leave encoded hashes alone (pbkdf2_sha256$… or legacy fixtures).
        if not value or value.startswith("pbkdf2"):
            return value
        if len(value) < 8:
            raise OperatorError(
                "dashboard password must be at least 8 characters.\n"
                "Fix: set a longer password in Settings → Dashboard",
                has_fix=False,
            )
        return DashboardPassword().hash(value)

    def redact_document(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        out = dict(raw)
        github = out.get("github")
        if isinstance(github, dict):
            out["github"] = self._redact_github(github)
        notifications = out.get("notifications")
        if isinstance(notifications, dict):
            out["notifications"] = self._redact_notifications(notifications)
        dashboard = out.get("dashboard")
        if isinstance(dashboard, dict):
            out["dashboard"] = self._redact_dashboard(dashboard)
        return out

    def _redact_github(self, github: Mapping[str, Any]) -> dict[str, Any]:
        out = dict(github)
        if out.get("clientSecret"):
            out["clientSecret"] = SettingsRedactor._MASK
        return out

    def _redact_dashboard(self, dashboard: Mapping[str, Any]) -> dict[str, Any]:
        out = dict(dashboard)
        auth = out.get("auth")
        if not isinstance(auth, dict):
            return out
        auth_out = dict(auth)
        if auth_out.get("passwordHash"):
            auth_out["passwordHash"] = SettingsRedactor._MASK
        auth_out["users"] = self._redact_password_users(auth_out.get("users"))
        out["auth"] = auth_out
        return out

    def _redact_password_users(self, users: Any) -> Any:
        if not isinstance(users, list):
            return users
        out = []
        for user in users:
            if not isinstance(user, dict):
                out.append(user)
                continue
            item = dict(user)
            if item.get("passwordHash"):
                item["passwordHash"] = SettingsRedactor._MASK
            out.append(item)
        return out

    def _redact_notifications(self, notifications: Mapping[str, Any]) -> dict[str, Any]:
        out = dict(notifications)
        channels = out.get("channels")
        if not isinstance(channels, list):
            return out
        redacted = []
        for channel in channels:
            if not isinstance(channel, dict):
                redacted.append(channel)
                continue
            item = dict(channel)
            settings = item.get("settings")
            if isinstance(settings, dict):
                item["settings"] = self._redactor.redact(settings)
            redacted.append(item)
        out["channels"] = redacted
        return out
