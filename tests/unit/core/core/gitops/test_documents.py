"""GitOps document schemas: notifications, rbac, disable_tips."""

from pathlib import Path

from raft.core.core.gitops.firewall_gitops import FirewallGitops
from raft.core.core.gitops.notifications_document import NotificationsDocument
from raft.core.core.gitops.notifications_gitops import NotificationsGitops
from raft.core.core.gitops.rbac_gitops import RbacGitops
from raft.core.core.gitops.alerts_gitops import AlertsGitops
from raft.core.core.rbac.document import RbacDocument
from raft.core.core.models.firewall import FirewallDocument
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.model.document import AlertRulesDocument
from tests.unit.base import RaftTestCase


class TestGitopsDocuments(RaftTestCase):
    def test_firewall_disable_tips(self) -> None:
        doc = FirewallDocument.from_mapping(
            {"version": 1, "disableTips": True, "rules": []},
            path="host/firewall.yaml",
        )
        assert doc.disable_tips is True
        assert doc.to_export()["disableTips"] is True

    def test_alerts_disable_tips(self) -> None:
        doc = AlertRulesDocument.from_mapping(
            {"version": 1, "disable_tips": True, "rules": []},
            registries=AlertCatalogs.default(),
            path="host/alerts.yaml",
        )
        assert doc.disable_tips is True

    def test_notifications_parse(self) -> None:
        doc = NotificationsDocument.from_mapping(
            {
                "enabled": True,
                "channels": [
                    {
                        "id": "ops-webhook",
                        "type": "webhook",
                        "settings": {"url": "https://hooks.example.invalid/x"},
                    }
                ],
            },
            path="host/notifications.yaml",
        )
        assert doc.config.channels[0].id == "ops-webhook"
        assert doc.to_export()["channels"][0]["type"] == "webhook"

    def test_rbac_parse(self) -> None:
        doc = RbacDocument.from_mapping(
            {
                "version": 1,
                "roles": [
                    {"id": "admin", "permissions": ["*:read", "*:write"]},
                    {"id": "viewer", "permissions": ["firewall:read"]},
                ],
                "bindings": [{"subject": "Ops@Example.com", "role": "admin"}],
            },
            path="host/rbac.yaml",
        )
        assert doc.roles[0].id == "admin"
        assert doc.bindings[0].subject == "ops@example.com"
        assert "*:write" in doc.permissions_for("ops@example.com")

    def test_gitops_loaders_empty_missing(self) -> None:
        home = Path(self.tmp_path)
        assert FirewallGitops(home).load().rules == ()
        assert AlertsGitops(home).load().rules == ()
        assert NotificationsGitops(home).load().config.channels == ()
        rbac = RbacGitops(home)
        assert rbac.load().roles == ()
        assert rbac.path() == home / "host" / "rbac.yaml"
