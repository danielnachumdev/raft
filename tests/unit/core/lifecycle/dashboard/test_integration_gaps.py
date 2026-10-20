"""Coverage for stack/ACME/firewall/status/serve dashboard wiring."""

from pathlib import Path
from unittest.mock import MagicMock

import yaml

from raft.core.core.config.settings.types import AcmeConfig
from raft.core.core.models.stack import load_stack
from raft.core.lifecycle.acme.ensure import AcmeEnsure
from raft.core.lifecycle.firewall.eligibility import FirewallEligibility
from raft.core.lifecycle.firewall.from_inspection import InspectionFirewall
from raft.core.lifecycle.firewall.service import FirewallService
from raft.core.observe.ops.status import Status
from raft.services.serve.http.instructions import ServeInstructions
from raft.services.serve.service import Serve
from tests.unit.base import RaftTestCase, StackMakers
from tests.unit.core.lifecycle.acme.cert_helpers import self_signed_pem


class TestDashboardIntegrationGaps(RaftTestCase):
    def _enable_public(self, home: Path) -> None:
        (home / "host" / "settings.yaml").write_text(
            yaml.safe_dump(
                {
                    "edge": {"http": 80, "https": 443},
                    "dashboard": {
                        "enabled": True,
                        "publicHost": "ops.example.com",
                        "tls": "acme",
                        "auth": {
                            "mode": "password",
                            "passwordHash": "pbkdf2_sha256$1$a$b",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )

    def test_core_services_includes_dashboard(self) -> None:
        home = Path(self.tmp_path)
        self._enable_public(home)
        assert "raft-dashboard" in load_stack(home).core_services

    def test_dashboard_enabled_tolerates_bad_settings(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text("- bad\n", encoding="utf-8")
        assert "raft-dashboard" not in load_stack(home).core_services

    def test_acme_run_includes_dashboard(self) -> None:
        home = Path(self.tmp_path)
        self._enable_public(home)
        runner = MagicMock()
        runner.issue.return_value = self_signed_pem(["ops.example.com"])
        AcmeEnsure(
            load_stack(home),
            order_runner=runner,
            config=AcmeConfig(email="ops@example.com"),
        ).run()
        assert (home / "services" / "raft-dashboard" / "certs" / "acme.pem").is_file()

    def test_firewall_dashboard_supported(self) -> None:
        home = Path(self.tmp_path)
        self._enable_public(home)
        stack = load_stack(home)
        assert FirewallEligibility(stack).meta("raft-dashboard")["supported"]
        names = [
            s["name"]
            for s in FirewallService(stack, orchestrator=MagicMock()).services()[
                "services"
            ]
        ]
        assert "raft-dashboard" in names
        found = InspectionFirewall(stack)._find_app_name("raft-dashboard")
        assert found == "raft-dashboard"

    def test_firewall_dashboard_unsupported(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text(
            "dashboard: {enabled: true}\n", encoding="utf-8"
        )
        stack = load_stack(home)
        assert not FirewallEligibility(stack).meta("raft-dashboard")["supported"]
        assert InspectionFirewall(stack)._find_app_name("raft-dashboard") is None

    def test_status_edge_targets_include_dashboard(self) -> None:
        home = Path(self.tmp_path)
        self._enable_public(home)
        targets = Status(load_stack(home))._edge_targets()
        assert any(t[0] == "raft-dashboard" and t[1] == "dashboard" for t in targets)

    def test_serve_control_plane_lists_dashboard(self) -> None:
        from raft.core.observe.ops.status.models import StatusSnapshot
        from raft.core.observe.read import ServeSnapshotView
        from tests.unit.core.observe.ops.status import fixtures as status_fx

        snap = StatusSnapshot(
            host=status_fx.empty_host_status(),
            containers=(
                status_fx.container("raft-gate", role="gate", group="raft"),
                status_fx.container("raft-dashboard", role="dashboard", group="raft"),
            ),
        )
        names = [r.name for r in ServeSnapshotView(snap).control_plane()]
        assert names == ["gate", "dashboard"]

    def test_instructions_always_on(self) -> None:
        text = ServeInstructions(
            8787,
            always_on_url="http://127.0.0.1:8787/",
            public_url="https://ops.example.com/",
        ).render()
        assert "Always-on dashboard" in text
        assert "ops.example.com" in text
        local_only = ServeInstructions(
            8787, always_on_url="http://127.0.0.1:8787/"
        ).render()
        assert "Always-on dashboard" in local_only
        assert "Public URL" not in local_only

    def test_serve_always_on_urls(self) -> None:
        home = Path(self.tmp_path)
        self._enable_public(home)
        urls = Serve(StackMakers.make_stack(home))._always_on_urls()
        assert urls["always_on_url"] == "http://127.0.0.1:8787/"
        assert urls["public_url"] == "https://ops.example.com/"
        (home / "host" / "settings.yaml").write_text(
            "dashboard: {enabled: true, port: 8787}\n", encoding="utf-8"
        )
        local = Serve(StackMakers.make_stack(home))._always_on_urls()
        assert local["always_on_url"]
        assert "public_url" not in local

    def test_serve_urls_disabled_and_error(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text("{}\n", encoding="utf-8")
        assert Serve(StackMakers.make_stack(home))._always_on_urls() == {}
        (home / "host" / "settings.yaml").write_text("- bad\n", encoding="utf-8")
        assert Serve(StackMakers.make_stack(home))._always_on_urls() == {}
