"""Coverage for GitOps loaders and RBAC schema edges."""

from pathlib import Path

import pytest
import yaml

from raft.core.core.errors.cta import OperatorError
from raft.core.core.gitops import (
    FirewallGitops,
    GitopsPathResolve,
    NotificationsGitops,
    RbacDocument,
    RbacGitops,
)
from raft.core.core.gitops.alerts_gitops import AlertsGitops
from raft.core.core.gitops.settings_gitops import SettingsGitops
from raft.core.core.models.firewall import FirewallDocument
from raft.core.observe.alerts.store.rules_store import AlertRulesStore
from tests.unit.base import RaftTestCase


class TestGitopsLoadersCoverage(RaftTestCase):
    def _write_host_yamls(self) -> Path:
        home = Path(self.tmp_path)
        host = home / "host"
        host.mkdir(parents=True, exist_ok=True)
        files = {
            "settings.yaml": "edge: {http: 80}\n",
            "firewall.yaml": "version: 1\nrules: []\n",
            "alerts.yaml": "version: 1\nrules: []\n",
            "notifications.yaml": "enabled: true\nchannels: []\n",
            "rbac.yaml": (
                "version: 1\nroles:\n"
                "  - id: admin\n"
                "    permissions: ['*:read', '*:write']\n"
                "bindings: []\n"
            ),
        }
        for name, text in files.items():
            (host / name).write_text(text, encoding="utf-8")
        return home

    def test_settings_and_firewall_load(self) -> None:
        home = self._write_host_yamls()
        settings = SettingsGitops(home)
        assert settings.load().edge.http == 80
        settings.clear_cache()
        fw = FirewallGitops(home)
        assert fw.load().version == 1
        fw.clear_cache()

    def test_alerts_notifications_rbac_load(self) -> None:
        home = self._write_host_yamls()
        alerts = AlertsGitops(home)
        assert alerts.load().version == 1
        alerts.clear_cache()
        note = NotificationsGitops(home)
        assert note.load().config.enabled is True
        note.clear_cache()
        rbac = RbacGitops(home)
        assert rbac.load().roles[0].id == "admin"
        rbac.clear_cache()

    def test_unknown_doc_kind(self) -> None:
        with pytest.raises(OperatorError, match="unknown GitOps"):
            GitopsPathResolve(Path(self.tmp_path)).path(object())  # type: ignore[arg-type]

    def test_firewall_disable_tips_snake(self) -> None:
        doc = FirewallDocument.from_mapping(
            {"version": 1, "disable_tips": True, "rules": []},
            path="host/firewall.yaml",
        )
        assert doc.disable_tips is True

    def test_rbac_null_and_type_errors(self) -> None:
        path = "host/rbac.yaml"
        assert RbacDocument.from_mapping(None, path=path).roles == ()
        with pytest.raises(OperatorError, match="must be a mapping"):
            RbacDocument.from_mapping([], path=path)
        with pytest.raises(OperatorError, match="must be an integer"):
            RbacDocument.from_mapping({"version": "x"}, path=path)
        with pytest.raises(OperatorError, match="unsupported version"):
            RbacDocument.from_mapping({"version": 2}, path=path)

    def test_rbac_roles_bindings_errors(self) -> None:
        path = "host/rbac.yaml"
        with pytest.raises(OperatorError, match="list of role"):
            RbacDocument.from_mapping({"roles": "admin"}, path=path)
        with pytest.raises(OperatorError, match="must be a mapping"):
            RbacDocument.from_mapping({"roles": [" "]}, path=path)
        with pytest.raises(OperatorError, match="must be a list"):
            RbacDocument.from_mapping({"bindings": {}}, path=path)
        with pytest.raises(OperatorError, match="must be a mapping"):
            RbacDocument.from_mapping({"bindings": ["x"]}, path=path)
        with pytest.raises(OperatorError, match="not defined"):
            RbacDocument.from_mapping(
                {
                    "roles": [{"id": "viewer", "permissions": ["firewall:read"]}],
                    "bindings": [{"subject": "ops@example.com", "role": "admin"}],
                },
                path=path,
            )

    def test_rbac_binding_subject_and_export(self) -> None:
        path = "host/rbac.yaml"
        with pytest.raises(OperatorError, match="requires subject"):
            RbacDocument.from_mapping(
                {"bindings": [{"subject": "", "role": "admin"}]}, path=path
            )
        empty = RbacDocument.from_mapping({"version": 1}, path=path)
        assert empty.to_export()["roles"] == []
        assert empty.permissions_for("") == frozenset()

    def test_rbac_role_permission_edges(self) -> None:
        path = "host/rbac.yaml"
        with pytest.raises(OperatorError, match="non-empty string"):
            RbacDocument.from_mapping({"roles": [{"id": "  "}]}, path=path)
        ok = RbacDocument.from_mapping(
            {"roles": [{"id": "viewer", "permissions": None}]}, path=path
        )
        assert ok.roles[0].permissions == ()
        with pytest.raises(OperatorError, match="list of permission"):
            RbacDocument.from_mapping(
                {"roles": [{"id": "x", "permissions": "firewall:read"}]},
                path=path,
            )
        with pytest.raises(OperatorError, match="invalid permission"):
            RbacDocument.from_mapping(
                {"roles": [{"id": "x", "permissions": ["nope"]}]},
                path=path,
            )

    def test_alert_store_load_raw_missing(self) -> None:
        store = AlertRulesStore(Path(self.tmp_path))
        with pytest.raises(OperatorError, match="missing"):
            store.load_raw()
        path = Path(self.tmp_path) / "host" / "alerts.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"version": 1, "rules": []}), encoding="utf-8")
        assert store.load_raw()["version"] == 1
