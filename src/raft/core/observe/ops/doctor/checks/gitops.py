"""Validate flat GitOps host YAML documents (settings/firewall/alerts/…)."""

from pathlib import Path

from raft.core.core.config.paths.host_paths import HostPaths
from raft.core.core.config.settings import SettingsLoader
from raft.core.core.errors.cta import OperatorError
from raft.core.core.gitops.alerts_gitops import AlertsGitops
from raft.core.core.gitops.cached_load import CachedYamlLoad
from raft.core.core.gitops.firewall_gitops import FirewallGitops
from raft.core.core.gitops.notifications_gitops import NotificationsGitops
from raft.core.core.gitops.rbac_gitops import RbacGitops

from ..context import DoctorContext
from ..models import INFRA, CheckResult


class GitopsChecks:
    """Parse each flat GitOps doc; missing files are ok (defaults / empty)."""

    name = "gitops"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        home = ctx.stack.root
        return [
            self._settings(home),
            self._firewall(home),
            self._alerts(home),
            self._notifications(home),
            self._rbac(home),
        ]

    def _settings(self, home: Path) -> CheckResult:
        path = HostPaths(home).settings()
        if not path.is_file():
            return self._absent("settings.yaml")
        try:
            raw = CachedYamlLoad().mapping(path, label="host/settings.yaml")
            SettingsLoader().from_raw(self._settings_body(raw))
        except OperatorError as exc:
            return self._invalid("settings.yaml", exc)
        return self._ok("settings.yaml")

    @staticmethod
    def _settings_body(raw: object) -> object:
        if not isinstance(raw, dict):
            return raw
        return {key: value for key, value in raw.items() if key != "notifications"}

    def _firewall(self, home: Path) -> CheckResult:
        path = HostPaths(home).firewall()
        if not path.is_file():
            return self._absent("firewall.yaml")
        try:
            FirewallGitops(home).load()
        except OperatorError as exc:
            return self._invalid("firewall.yaml", exc)
        return self._ok("firewall.yaml")

    def _alerts(self, home: Path) -> CheckResult:
        path = HostPaths(home).alerts()
        if not path.is_file():
            return self._absent("alerts.yaml")
        try:
            AlertsGitops(home).load()
        except OperatorError as exc:
            return self._invalid("alerts.yaml", exc)
        return self._ok("alerts.yaml")

    def _notifications(self, home: Path) -> CheckResult:
        path = HostPaths(home).notifications()
        if not path.is_file():
            return self._absent("notifications.yaml")
        try:
            NotificationsGitops(home).load()
        except OperatorError as exc:
            return self._invalid("notifications.yaml", exc)
        return self._ok("notifications.yaml")

    def _rbac(self, home: Path) -> CheckResult:
        path = HostPaths(home).rbac()
        if not path.is_file():
            return self._absent("rbac.yaml")
        try:
            RbacGitops(home).load()
        except OperatorError as exc:
            return self._invalid("rbac.yaml", exc)
        return self._ok("rbac.yaml")

    @staticmethod
    def _absent(name: str) -> CheckResult:
        return CheckResult(INFRA, name, "ok", "absent (defaults)")

    @staticmethod
    def _ok(name: str) -> CheckResult:
        return CheckResult(INFRA, name, "ok", f"host/{name} valid")

    @staticmethod
    def _invalid(name: str, exc: OperatorError) -> CheckResult:
        detail = str(exc).split("\n")[0]
        return CheckResult(
            INFRA,
            name,
            "fail",
            f"host/{name} invalid: {detail}",
            fix=f"repair ~/.raft/host/{name}",
        )
