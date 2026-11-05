"""Integration story: doctor validates flat GitOps host docs (#411)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from raft.core.observe.ops.doctor.checks.gitops import GitopsChecks
from raft.core.observe.ops.doctor.context import DoctorContext
from raft.core.observe.ops.doctor.models import INFRA
from tests.shared.raft_home import RaftHomeFixtures
from tests.shared.yaml_doc import YamlDoc
from tests.unit.base import ShellMocks, StackMakers

pytestmark = pytest.mark.integration


class TestGitopsDoctorFlatDocsStory:
    """Operator Syncs flat host YAML; doctor fails on invalid notifications/rbac.

    Scenario:
      1) Valid flat docs (settings/firewall/alerts/notifications/rbac) → ok.
      2) Corrupt notifications.yaml → FAIL naming host/notifications.yaml.
      3) Corrupt rbac.yaml → FAIL naming host/rbac.yaml.
    """

    def test_valid_then_invalid_notifications_and_rbac(
        self, isolated_raft_env: Path
    ) -> None:
        home = isolated_raft_env
        RaftHomeFixtures.prepare(home)
        self._seed_valid_flat_docs(home)
        self._assert_all_ok(home)
        self._assert_doc_fails(
            home, "notifications.yaml", "channels: not-a-list\n"
        )
        self._assert_doc_fails(
            home, "rbac.yaml", "version: 1\nroles: not-a-list\n"
        )

    def _seed_valid_flat_docs(self, home: Path) -> None:
        host = home / "host"
        YamlDoc(host / "firewall.yaml").dump({"version": 1, "rules": []})
        YamlDoc(host / "alerts.yaml").dump({"version": 1, "rules": []})
        YamlDoc(host / "notifications.yaml").dump(
            {"enabled": True, "channels": []}
        )
        YamlDoc(host / "rbac.yaml").dump(
            {"version": 1, "roles": [], "bindings": []}
        )

    def _assert_all_ok(self, home: Path) -> None:
        rows = self._gitops_rows(home)
        for name in (
            "settings.yaml",
            "firewall.yaml",
            "alerts.yaml",
            "notifications.yaml",
            "rbac.yaml",
        ):
            assert rows[(INFRA, name)].status == "ok"

    def _assert_doc_fails(self, home: Path, name: str, body: str) -> None:
        (home / "host" / name).write_text(body, encoding="utf-8")
        row = self._gitops_rows(home)[(INFRA, name)]
        assert row.status == "fail"
        assert name in row.detail

    def _gitops_rows(self, home: Path):
        stack = StackMakers.make_stack(home, ())
        docker = MagicMock()
        shell = ShellMocks.stub_run(MagicMock(), returncode=0)
        ctx = DoctorContext(stack=stack, shell=shell, auth=None, docker=docker)
        return {(r.service, r.check): r for r in GitopsChecks().run(ctx)}
