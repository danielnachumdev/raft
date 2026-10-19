"""AcmeEnsure skip / issue / lastError (mocked order runner)."""

from __future__ import annotations

from unittest.mock import MagicMock

from raft.core.core.config.settings.types import AcmeConfig
from raft.core.core.models.stack import load_stack
from raft.core.lifecycle.acme.app_store import AcmeAppStore
from raft.core.lifecycle.acme.ensure import AcmeEnsure
from raft.core.lifecycle.acme.install import AcmeGateInstall

from .cert_helpers import plant_live_acme, self_signed_pem
from tests.unit.base import RaftTestCase, AppliedInventory


class TestAcmeEnsure(RaftTestCase):
    def test_missing_email_records_error(self) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "web", public_host="web.test", tls="acme")
        stack = load_stack(self.tmp_path)
        store = AcmeAppStore(self.tmp_path)
        AcmeEnsure(stack, store=store, config=AcmeConfig(email=None)).run(["web"])
        assert "acme.email" in (store.load("web").last_error or "")

    def test_issue_success_and_install(self) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "web", public_host="web.test", tls="acme")
        stack = load_stack(self.tmp_path)
        runner = MagicMock()
        runner.issue.return_value = self_signed_pem(["web.test"])
        installer = MagicMock(spec=AcmeGateInstall)
        store = AcmeAppStore(self.tmp_path)
        AcmeEnsure(
            stack,
            order_runner=runner,
            installer=installer,
            store=store,
            config=AcmeConfig(email="ops@example.com"),
        ).run(["web"])
        assert (self.tmp_path / "certs" / "web" / "acme.pem").is_file()
        assert store.load("web").last_error is None
        installer.apply.assert_called_once()

    def test_issue_failure_persists_last_error(self) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "web", public_host="web.test", tls="acme")
        stack = load_stack(self.tmp_path)
        runner = MagicMock()
        runner.issue.side_effect = RuntimeError("DNS not ready")
        store = AcmeAppStore(self.tmp_path)
        AcmeEnsure(
            stack,
            order_runner=runner,
            store=store,
            config=AcmeConfig(email="ops@example.com"),
        ).run(["web"])
        assert "DNS not ready" in (store.load("web").last_error or "")

    def test_skips_fresh_cert(self) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "web", public_host="web.test", tls="acme")
        plant_live_acme(self.tmp_path, "web", ["web.test"], days=60)
        runner = MagicMock()
        AcmeEnsure(
            load_stack(self.tmp_path),
            order_runner=runner,
            config=AcmeConfig(email="ops@example.com", renew_days_before_expiry=30),
        ).run(["web"])
        runner.issue.assert_not_called()

    def test_renews_near_expiry(self) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "web", public_host="web.test", tls="acme")
        plant_live_acme(self.tmp_path, "web", ["web.test"], days=10)
        runner = MagicMock()
        runner.issue.return_value = self_signed_pem(["web.test"])
        AcmeEnsure(
            load_stack(self.tmp_path),
            order_runner=runner,
            config=AcmeConfig(email="ops@example.com", renew_days_before_expiry=30),
        ).run(["web"])
        runner.issue.assert_called_once()

    def test_ignores_non_acme(self) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "web", public_host="web.test", tls="off")
        runner = MagicMock()
        AcmeEnsure(
            load_stack(self.tmp_path),
            order_runner=runner,
            config=AcmeConfig(email="ops@example.com"),
        ).run()
        runner.issue.assert_not_called()

    def test_named_dashboard_skipped_when_not_acme(self) -> None:
        runner = MagicMock()
        AcmeEnsure(
            load_stack(self.tmp_path),
            order_runner=runner,
            config=AcmeConfig(email="ops@example.com"),
        ).run(["raft-dashboard"])
        runner.issue.assert_not_called()

    def test_named_dashboard_issues_when_acme(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "dashboard:\n  enabled: true\n  publicHost: ops.example.com\n"
            "  tls: acme\n  auth: {mode: password, passwordHash: pbkdf2_sha256$1$a$b}\n",
            encoding="utf-8",
        )
        runner = MagicMock()
        runner.issue.return_value = self_signed_pem(["ops.example.com"])
        AcmeEnsure(
            load_stack(self.tmp_path),
            order_runner=runner,
            config=AcmeConfig(email="ops@example.com"),
        ).run(["raft-dashboard"])
        runner.issue.assert_called_once()
        assert (self.tmp_path / "certs" / "raft-dashboard" / "acme.pem").is_file()
