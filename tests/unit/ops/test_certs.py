"""Origin cert preflight helpers."""

import pytest

from raft.errors.certs_msgs import looks_like_missing_origin_cert
from raft.ops.certs import CertProbe

from tests.unit.base import RaftTestCase, write_applied_app


class TestOriginCerts(RaftTestCase):
    def test_missing_and_require(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="origin")
        from raft.models.stack import load_stack

        stack = load_stack(self.tmp_path)
        missing = CertProbe(stack).missing_origin()
        assert len(missing) == 1
        assert missing[0].app_name == "web"
        assert "origin.pem" in missing[0].missing
        with pytest.raises(RuntimeError, match="Origin certs missing"):
            CertProbe(stack).require_origin()

        d = self.tmp_path / "certs" / "web"
        d.mkdir(parents=True)
        (d / "origin.pem").write_text("pem\n", encoding="utf-8")
        (d / "origin.key").write_text("key\n", encoding="utf-8")
        assert CertProbe(load_stack(self.tmp_path)).missing_origin() == []
        CertProbe(load_stack(self.tmp_path)).require_origin()

    def test_tls_off_ignored(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="off")
        from raft.models.stack import load_stack

        assert CertProbe(load_stack(self.tmp_path)).missing_origin() == []

    def test_tls_acme_ignored_by_origin_require(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="acme")
        from raft.models.stack import load_stack

        stack = load_stack(self.tmp_path)
        probe = CertProbe(stack)
        assert probe.missing_origin() == []
        probe.require_origin()
        missing = probe.missing_acme()
        assert len(missing) == 1
        assert "acme.pem" in missing[0].missing
        assert "DNS" in missing[0].fix
        assert "Cloudflare" not in missing[0].fix

    def test_looks_like_missing_origin_cert(self) -> None:
        nginx = (
            'cannot load certificate "/etc/nginx/certs/web/origin.pem": ' "BIO_new_file() failed"
        )
        assert looks_like_missing_origin_cert(nginx)
        assert looks_like_missing_origin_cert("BIO_new_file() failed while opening origin.pem")
        assert not looks_like_missing_origin_cert("connection refused")
        acme = 'cannot load certificate "/etc/nginx/certs/web/acme.pem"'
        assert not looks_like_missing_origin_cert(acme)
        from raft.errors.certs_msgs import looks_like_missing_acme_cert

        assert looks_like_missing_acme_cert(acme)
        assert looks_like_missing_acme_cert("BIO_new_file() failed while opening acme.key")
