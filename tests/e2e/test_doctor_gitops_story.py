"""E2E story: doctor report surfaces invalid flat GitOps notifications (#411)."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from raft.core.core.models.stack import load_stack
from raft.core.observe.ops.doctor import Doctor
from tests.shared.raft_home import RaftHomeFixtures
from tests.shared.yaml_doc import YamlDoc

pytestmark = pytest.mark.e2e


class TestDoctorGitopsNotificationsStory:
    """Operator lands a bad notifications.yaml; doctor names the flat SoT path.

    Scenario:
      1) Host has otherwise-valid flat GitOps docs.
      2) notifications.yaml channels are corrupt.
      3) ``raft doctor`` report cites notifications.yaml under FAIL.
    """

    def test_invalid_notifications_named_in_doctor_report(
        self, isolated_raft_env: Path
    ) -> None:
        home = isolated_raft_env
        RaftHomeFixtures.apply_and_render(
            home, RaftHomeFixtures.fixture_app_yamls("http_only")
        )
        self._seed_sidecar_docs(home)
        (home / "host" / "notifications.yaml").write_text(
            "channels: not-a-list\n", encoding="utf-8"
        )
        out = StringIO()
        Doctor(load_stack(home)).report(out=out, color=False)
        text = out.getvalue()
        assert "FAIL" in text
        assert "notifications.yaml" in text

    def _seed_sidecar_docs(self, home: Path) -> None:
        host = home / "host"
        YamlDoc(host / "firewall.yaml").dump({"version": 1, "rules": []})
        YamlDoc(host / "alerts.yaml").dump({"version": 1, "rules": []})
        YamlDoc(host / "rbac.yaml").dump(
            {"version": 1, "roles": [], "bindings": []}
        )
