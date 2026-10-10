"""Origin cert preflight helpers."""

import pytest

from raft.ops.certs import (
    looks_like_missing_origin_cert,
    missing_origin_certs,
    require_origin_certs,
)

from tests.unit.base import RaftTestCase, write_applied_app


class TestOriginCerts(RaftTestCase):
    def test_missing_and_require(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="origin")
        from raft.models.stack import load_stack

        stack = load_stack(self.tmp_path)
        missing = missing_origin_certs(stack)
        assert len(missing) == 1
        assert missing[0].app_name == "web"
        assert "origin.pem" in missing[0].missing
        with pytest.raises(RuntimeError, match="Origin certs missing"):
            require_origin_certs(stack)

        d = self.tmp_path / "certs" / "web"
        d.mkdir(parents=True)
        (d / "origin.pem").write_text("pem\n", encoding="utf-8")
        (d / "origin.key").write_text("key\n", encoding="utf-8")
        assert missing_origin_certs(load_stack(self.tmp_path)) == []
        require_origin_certs(load_stack(self.tmp_path))

    def test_tls_off_ignored(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="off")
        from raft.models.stack import load_stack

        assert missing_origin_certs(load_stack(self.tmp_path)) == []

    def test_tls_acme_ignored_by_origin_require(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="acme")
        from raft.models.stack import load_stack

        stack = load_stack(self.tmp_path)
        assert missing_origin_certs(stack) == []
        require_origin_certs(stack)
        from raft.ops.certs import missing_acme_certs

        missing = missing_acme_certs(stack)
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
