"""Doctor dashboard oauth readiness warnings."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from raft.core.lifecycle.dashboard.settings_write import DashboardSettingsWriter
from raft.core.observe.ops.doctor.models import INFRA
from tests.unit.base import StackMakers
from tests.unit.core.lifecycle.dashboard.oauth_test_helpers import seed_oauth_secrets
from tests.unit.core.observe.ops.doctor.base import DoctorTestCase

_OAUTH_SETTINGS = """\
dashboard:
  enabled: true
  port: 8787
  publicHost: ops.example.com
  tls: acme
  auth:
    mode: oauth
    oauth:
      provider: google
"""


class TestDoctorDashboardOauth(DoctorTestCase):
    def test_skips_when_dashboard_disabled(self) -> None:
        self._seed_home()
        results = self.run_keyed(
            StackMakers.make_stack(self.tmp_path, ()),
            shell=self.mock_shell(),
            docker=self.mock_docker(),
            auth=MagicMock(),
        )
        assert (INFRA, "dashboard_oauth") not in results

    def test_warns_when_oauth_secrets_missing(self) -> None:
        self._seed_home(settings=_OAUTH_SETTINGS)
        results = self.run_keyed(
            StackMakers.make_stack(self.tmp_path, ()),
            shell=self.mock_shell(),
            docker=self.mock_docker(),
            auth=MagicMock(),
        )
        row = results[(INFRA, "dashboard_oauth")]
        assert row.status == "warn"
        assert "oauth" in row.detail.lower()
        assert "OAUTH2_PROXY_CLIENT_ID" in row.fix

    def test_ok_when_secrets_ready(self) -> None:
        home = Path(self.tmp_path)
        self._seed_home()
        seed_oauth_secrets(home)
        DashboardSettingsWriter(home).enable(
            public_host="ops.example.com",
            tls="acme",
            auth_mode="oauth",
        )
        results = self.run_keyed(
            StackMakers.make_stack(self.tmp_path, ()),
            shell=self.mock_shell(),
            docker=self.mock_docker(),
            auth=MagicMock(),
        )
        row = results[(INFRA, "dashboard_oauth")]
        assert row.status == "ok"

    def _seed_home(self, *, settings: str = "{}\n") -> None:
        self.seed_compose()
        self.seed_generated_apps()
        host = self.tmp_path / "host"
        host.mkdir(parents=True, exist_ok=True)
        (host / "settings.yaml").write_text(settings, encoding="utf-8")
