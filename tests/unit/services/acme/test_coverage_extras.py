"""Extra branch coverage for ACME account / ensure / material / msgs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from acme import challenges
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from raft.config.settings_types import AcmeConfig
from raft.errors.certs_msgs import (
    format_missing_acme_certs,
    looks_like_missing_acme_cert,
    missing_acme_certs_fallback,
)
from raft.models.stack import load_stack
from raft.services.acme.account import AcmeAccountStore
from raft.services.acme.app_store import AcmeAppState, AcmeAppStore
from raft.services.acme.ensure import AcmeEnsure
from raft.services.acme.material import AcmeCertMaterial
from raft.services.acme.order import AcmeOrderRunner
from raft.services.acme.paths import AcmePaths
from raft.services.ops.certs import MissingAcmeCerts

from .cert_helpers import plant_live_acme
from ...base import RaftTestCase, write_applied_app


class TestAcmeCoverageExtras(RaftTestCase):
    def test_account_non_dict_and_bad_body(self) -> None:
        store = AcmeAccountStore(self.tmp_path)
        paths = AcmePaths(self.tmp_path)
        paths.ensure_dirs()
        paths.account_json.write_text("[]\n", encoding="utf-8")
        assert store._load_registration("https://x/dir") is None
        paths.account_json.write_text(
            '{"directory":"https://x/dir","uri":"","body":{}}\n', encoding="utf-8"
        )
        assert store._load_registration("https://x/dir") is None

    def test_account_corrupt_registration_body(self) -> None:
        store = AcmeAccountStore(self.tmp_path)
        paths = AcmePaths(self.tmp_path)
        paths.ensure_dirs()
        paths.account_json.write_text(
            '{"directory":"https://x/dir","uri":"u","body":{"status":"valid"}}\n',
            encoding="utf-8",
        )
        with patch(
            "raft.services.acme.account.messages.Registration.from_json",
            side_effect=ValueError("bad"),
        ):
            assert store._load_registration("https://x/dir") is None

    def test_ensure_skips_off_mode(self) -> None:
        write_applied_app(self.tmp_path, "off", public_host="off.test", tls="off")
        stack = load_stack(self.tmp_path)
        ensure = AcmeEnsure(stack, config=AcmeConfig(email="ops@x.com"))
        assert ensure.ensure_app(stack.app("off")) is False

    def test_ensure_corrupt_pem_and_san_change(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="acme")
        ensure = AcmeEnsure(load_stack(self.tmp_path), config=AcmeConfig(email="ops@x.com"))
        d = self.tmp_path / "certs" / "web"
        d.mkdir(parents=True, exist_ok=True)
        (d / "acme.pem").write_text("not-a-cert\n", encoding="utf-8")
        (d / "acme.key").write_text("key\n", encoding="utf-8")
        assert ensure._should_skip("web", ["web.test"]) is False
        plant_live_acme(self.tmp_path, "web", ["other.test"], days=60)
        assert ensure._should_skip("web", ["web.test"]) is False

    def test_ensure_builds_default_runner(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="acme")
        ensure = AcmeEnsure(load_stack(self.tmp_path), config=AcmeConfig(email="ops@x.com"))
        with patch("raft.services.acme.ensure.AcmeAccountStore") as account_cls:
            with patch("raft.services.acme.ensure.AcmeOrderRunner") as runner_cls:
                runner = ensure._default_runner(email="ops@x.com")
        assert runner is runner_cls.return_value
        account_cls.assert_called_once()

    def test_ensure_is_acme_swallows_errors(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="acme")
        stack = load_stack(self.tmp_path)
        ensure = AcmeEnsure(stack, config=AcmeConfig(email="ops@x.com"))
        with patch.object(type(stack), "spec_for", side_effect=RuntimeError("boom")):
            assert ensure._is_acme(stack.app("web")) is False

    def test_material_without_san(self) -> None:
        assert AcmeCertMaterial.from_pem(_cert_pem_without_san()).names == ()

    def test_order_skips_non_http01_challenge(self) -> None:
        http = challenges.HTTP01(token=b"h" * 32)
        challb_http = MagicMock()
        challb_http.chall = http
        challb_http.response_and_validation.return_value = (MagicMock(), "v")
        other = MagicMock()
        other.chall = object()
        authz = MagicMock()
        authz.body.challenges = [other, challb_http]
        order = MagicMock(authorizations=[authz])
        client = MagicMock()
        client.new_order.return_value = order
        client.poll_and_finalize.return_value = MagicMock(fullchain_pem="CERT")
        out = AcmeOrderRunner(self.tmp_path, client_factory=lambda: client).issue(b"c")
        assert out == b"CERT"

    def test_app_store_atomic_write_cleans_tmp(self) -> None:
        store = AcmeAppStore(self.tmp_path)
        with patch("raft.services.acme.app_store.os.replace", side_effect=OSError("nope")):
            with patch("raft.services.acme.app_store.os.unlink", side_effect=OSError("gone")):
                with pytest.raises(OSError, match="nope"):
                    store.save("web", AcmeAppState(last_error="x"))

    def test_acme_cert_msg_helpers(self) -> None:
        assert looks_like_missing_acme_cert("BIO_new_file() failed acme.crt")
        text = format_missing_acme_certs(
            [MissingAcmeCerts("web", ("acme.pem",))],
            include_doctor_footer=True,
        )
        assert "Run `raft doctor`" in text
        assert "acme.pem" in missing_acme_certs_fallback(detail="")
        assert "detail" in missing_acme_certs_fallback(detail="detail")


def _cert_pem_without_san() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "x.test")]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "x.test")]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM)
