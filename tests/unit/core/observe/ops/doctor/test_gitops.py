"""Doctor GitOps flat-document validity checks."""

from raft.core.observe.ops.doctor.checks.gitops import GitopsChecks
from raft.core.observe.ops.doctor.context import DoctorContext
from raft.core.observe.ops.doctor.models import INFRA
from tests.unit.base import StackMakers
from tests.unit.core.observe.ops.doctor.base import DoctorTestCase


class TestDoctorGitops(DoctorTestCase):
    def test_absent_docs_are_ok(self) -> None:
        rows = self._gitops_rows()
        for name in (
            "settings.yaml",
            "firewall.yaml",
            "alerts.yaml",
            "notifications.yaml",
            "rbac.yaml",
        ):
            assert rows[(INFRA, name)].status == "ok"

    def test_valid_docs_ok(self) -> None:
        self._seed_valid()
        rows = self._gitops_rows()
        for name in (
            "settings.yaml",
            "firewall.yaml",
            "alerts.yaml",
            "notifications.yaml",
            "rbac.yaml",
        ):
            assert rows[(INFRA, name)].status == "ok"
            assert "valid" in rows[(INFRA, name)].detail

    def test_invalid_firewall_fails(self) -> None:
        self._seed_valid()
        path = self.tmp_path / "host" / "firewall.yaml"
        path.write_text("[]\n", encoding="utf-8")
        row = self._gitops_rows()[(INFRA, "firewall.yaml")]
        assert row.status == "fail"
        assert "host/firewall.yaml" in row.detail
        assert "host/firewall.yaml" in row.fix
        assert "rules.yaml" not in row.detail
        assert "nested" not in row.detail.lower()

    def test_invalid_notifications_fails(self) -> None:
        self._seed_valid()
        path = self.tmp_path / "host" / "notifications.yaml"
        path.write_text("channels: not-a-list\n", encoding="utf-8")
        row = self._gitops_rows()[(INFRA, "notifications.yaml")]
        assert row.status == "fail"
        assert "notifications.yaml" in row.detail

    def test_invalid_alerts_fails(self) -> None:
        self._seed_valid()
        path = self.tmp_path / "host" / "alerts.yaml"
        path.write_text("[]\n", encoding="utf-8")
        row = self._gitops_rows()[(INFRA, "alerts.yaml")]
        assert row.status == "fail"
        assert "alerts.yaml" in row.detail

    def test_settings_ignores_nested_notifications_key(self) -> None:
        host = self.tmp_path / "host"
        host.mkdir(parents=True, exist_ok=True)
        (host / "settings.yaml").write_text(
            "edge: {http: 80}\nnotifications: not-a-mapping\n",
            encoding="utf-8",
        )
        assert self._gitops_rows()[(INFRA, "settings.yaml")].status == "ok"

    def test_absent_settings_detail(self) -> None:
        empty = self.tmp_path / "empty-home"
        empty.mkdir()
        row = GitopsChecks()._settings(empty)
        assert row.status == "ok"
        assert "absent" in row.detail

    def test_invalid_settings_fails(self) -> None:
        host = self.tmp_path / "host"
        host.mkdir(parents=True, exist_ok=True)
        (host / "settings.yaml").write_text("edge: {http: nope}\n", encoding="utf-8")
        row = self._gitops_rows()[(INFRA, "settings.yaml")]
        assert row.status == "fail"
        assert "settings.yaml" in row.detail

    def test_invalid_rbac_fails(self) -> None:
        self._seed_valid()
        path = self.tmp_path / "host" / "rbac.yaml"
        path.write_text("version: 1\nroles: not-a-list\n", encoding="utf-8")
        row = self._gitops_rows()[(INFRA, "rbac.yaml")]
        assert row.status == "fail"
        assert "rbac.yaml" in row.detail

    def _seed_valid(self) -> None:
        host = self.tmp_path / "host"
        host.mkdir(parents=True, exist_ok=True)
        (host / "settings.yaml").write_text("edge: {http: 80}\n", encoding="utf-8")
        (host / "firewall.yaml").write_text(
            "version: 1\nrules: []\n", encoding="utf-8"
        )
        (host / "alerts.yaml").write_text(
            "version: 1\nrules: []\n", encoding="utf-8"
        )
        (host / "notifications.yaml").write_text(
            "enabled: true\nchannels: []\n", encoding="utf-8"
        )
        (host / "rbac.yaml").write_text(
            "version: 1\nroles: []\nbindings: []\n", encoding="utf-8"
        )

    def _gitops_rows(self):
        stack = StackMakers.make_stack(self.tmp_path, ())
        ctx = DoctorContext(
            stack=stack,
            shell=self.mock_shell(),
            auth=None,
            docker=self.mock_docker(),
        )
        return {(r.service, r.check): r for r in GitopsChecks().run(ctx)}


class TestGitopsChecksHelpers(DoctorTestCase):
    def test_settings_body_strips_notifications(self) -> None:
        body = GitopsChecks._settings_body(
            {"edge": {"http": 80}, "notifications": {"enabled": True}}
        )
        assert body == {"edge": {"http": 80}}
        assert GitopsChecks._settings_body([]) == []
