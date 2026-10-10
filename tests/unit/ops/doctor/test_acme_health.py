"""Doctor ACME cert health (email, edge.http, expiry, lastError)."""

from __future__ import annotations

from unittest.mock import MagicMock

from raft.config.settings_types import AcmeConfig, EdgeConfig, RaftConfig
from raft.acme.app_store import AcmeAppStore
from raft.ops.acme_health import AcmeCertHealth
from raft.models.stack import load_stack

from tests.unit.base import write_applied_app
from tests.unit.acme.cert_helpers import plant_live_acme
from .base import DoctorTestCase


class TestAcmeCertHealth(DoctorTestCase):
    def _write_settings(self, *, email: str | None = "ops@example.com", http=80) -> None:
        cfg = RaftConfig(
            edge=EdgeConfig(http=http, https=443),
            acme=AcmeConfig(email=email, renew_days_before_expiry=30),
        )
        # settings via yaml-ish through load_config path
        text = (
            "edge:\n"
            f"  http: {http if http is not None else 'null'}\n"
            "  https: 443\n"
            "acme:\n"
        )
        if email is not None:
            text += f"  email: {email}\n"
        text += "  renewDaysBeforeExpiry: 30\n"
        (self.tmp_path / "settings.yaml").write_text(text, encoding="utf-8")

    def test_fails_when_edge_http_null(self) -> None:
        self._write_settings(http=None)
        write_applied_app(self.tmp_path, "shop", public_host="shop.test", tls="acme")
        stack = load_stack(self.tmp_path)
        result = AcmeCertHealth(stack).check(stack.app("shop"), missing=None)
        assert result.status == "fail"
        assert "edge.http" in result.detail

    def test_fails_when_email_missing(self) -> None:
        self._write_settings(email=None)
        write_applied_app(self.tmp_path, "shop", public_host="shop.test", tls="acme")
        stack = load_stack(self.tmp_path)
        result = AcmeCertHealth(stack).check(stack.app("shop"), missing=None)
        assert result.status == "fail"
        assert "acme.email" in result.detail

    def test_missing_cert_includes_last_error(self) -> None:
        self._write_settings()
        write_applied_app(self.tmp_path, "shop", public_host="shop.test", tls="acme")
        store = AcmeAppStore(self.tmp_path)
        store.record_error("shop", "DNS not ready")
        from raft.ops.certs import MissingAcmeCerts

        stack = load_stack(self.tmp_path)
        missing = MissingAcmeCerts("shop", ("acme.pem", "acme.key"))
        result = AcmeCertHealth(stack, store=store).check(stack.app("shop"), missing)
        assert result.status == "fail"
        assert "lastError" in result.detail and "DNS not ready" in result.detail

    def test_ok_with_fresh_cert(self) -> None:
        self._write_settings()
        write_applied_app(self.tmp_path, "shop", public_host="shop.test", tls="acme")
        plant_live_acme(self.tmp_path, "shop", ["shop.test"], days=60)
        stack = load_stack(self.tmp_path)
        result = AcmeCertHealth(stack).check(stack.app("shop"), missing=None)
        assert result.status == "ok"
        assert "notAfter" in result.detail

    def test_warn_near_expiry(self) -> None:
        self._write_settings()
        write_applied_app(self.tmp_path, "shop", public_host="shop.test", tls="acme")
        plant_live_acme(self.tmp_path, "shop", ["shop.test"], days=10)
        stack = load_stack(self.tmp_path)
        result = AcmeCertHealth(stack).check(stack.app("shop"), missing=None)
        assert result.status == "warn"
        assert "renews soon" in result.detail

    def test_fail_expired(self) -> None:
        self._write_settings()
        write_applied_app(self.tmp_path, "shop", public_host="shop.test", tls="acme")
        plant_live_acme(self.tmp_path, "shop", ["shop.test"], days=-1)
        stack = load_stack(self.tmp_path)
        result = AcmeCertHealth(stack).check(stack.app("shop"), missing=None)
        assert result.status == "fail"
        assert "expired" in result.detail

    def test_unreadable_pem_fails(self) -> None:
        self._write_settings()
        write_applied_app(self.tmp_path, "shop", public_host="shop.test", tls="acme")
        d = self.tmp_path / "certs" / "shop"
        d.mkdir(parents=True)
        (d / "acme.pem").write_text("not-a-cert\n", encoding="utf-8")
        (d / "acme.key").write_text("key\n", encoding="utf-8")
        stack = load_stack(self.tmp_path)
        result = AcmeCertHealth(stack).check(stack.app("shop"), missing=None)
        assert result.status == "fail"
        assert "unreadable" in result.detail

    def test_warn_last_error_with_valid_cert(self) -> None:
        self._write_settings()
        write_applied_app(self.tmp_path, "shop", public_host="shop.test", tls="acme")
        plant_live_acme(self.tmp_path, "shop", ["shop.test"], days=60)
        store = AcmeAppStore(self.tmp_path)
        store.record_error("shop", "rateLimited")
        stack = load_stack(self.tmp_path)
        result = AcmeCertHealth(stack, store=store).check(stack.app("shop"), missing=None)
        assert result.status == "warn"
        assert "lastError" in result.detail
        assert result.fix and "staging" in result.fix

    def test_near_expiry_includes_last_error(self) -> None:
        self._write_settings()
        write_applied_app(self.tmp_path, "shop", public_host="shop.test", tls="acme")
        plant_live_acme(self.tmp_path, "shop", ["shop.test"], days=10)
        store = AcmeAppStore(self.tmp_path)
        store.record_error("shop", "temporary failure")
        stack = load_stack(self.tmp_path)
        result = AcmeCertHealth(stack, store=store).check(stack.app("shop"), missing=None)
        assert result.status == "warn"
        assert "lastError" in result.detail
        assert result.fix and "staging" not in result.fix


class TestDoctorAppFilter(DoctorTestCase):
    def test_filter_excludes_other_app_failures(self) -> None:
        self.seed_compose()
        self.ensure_checkouts("shop", "other")
        write_applied_app(self.tmp_path, "shop", public_host="shop.test", tls="acme")
        write_applied_app(self.tmp_path, "other", public_host="other.test", tls="origin")
        plant_live_acme(self.tmp_path, "shop", ["shop.test"], days=60)
        (self.tmp_path / "settings.yaml").write_text(
            "edge:\n  http: 80\n  https: 443\nacme:\n  email: ops@example.com\n",
            encoding="utf-8",
        )
        stack = load_stack(self.tmp_path)
        doctor = self.doctor(
            stack=stack, shell=self.mock_shell(), docker=self.mock_docker()
        )
        filtered = doctor.run(app_name="shop")
        assert all(r.service == "shop" for r in filtered)
        assert not any(r.service == "other" for r in filtered)
        code = doctor.report(results=filtered)
        assert code == 0
        all_results = doctor.run()
        assert any(r.service == "other" and r.status == "fail" for r in all_results)

    def test_unknown_app_raises(self) -> None:
        self.seed_compose()
        write_applied_app(self.tmp_path, "shop", public_host="shop.test", tls="off")
        doctor = self.doctor(
            stack=load_stack(self.tmp_path),
            shell=self.mock_shell(),
            docker=self.mock_docker(),
        )
        import pytest
        from raft.errors.cta import OperatorError

        with pytest.raises(OperatorError, match="unknown app"):
            doctor.run(app_name="missing")
