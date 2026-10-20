"""HTTP→HTTPS redirect fragments for tls: acme with live PEMs."""

from __future__ import annotations

from raft.core.core.config.settings.types import EdgeConfig
from raft.core.lifecycle.acme.http_redirect import AcmeHttpRedirect

from tests.unit.base import RaftTestCase, AppliedInventory

_EDGE = EdgeConfig(http=80, https=443, streams=())


class TestAcmeHttpRedirect(RaftTestCase):
    def test_no_redirect_without_pems(self) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "web", public_host="web.test", tls="acme")
        gen = self.render_applied(edge=_EDGE)
        conf = (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")
        assert "acme-redirect:web" not in conf
        assert "return 301 https://" not in conf

    def test_redirect_when_pems_exist(self) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "web", public_host="web.test", tls="acme")
        d = self.tmp_path / "services" / "web" / "certs"
        d.mkdir(parents=True, exist_ok=True)
        (d / "acme.pem").write_text("pem\n", encoding="utf-8")
        (d / "acme.key").write_text("key\n", encoding="utf-8")
        gen = self.render_applied(edge=_EDGE)
        conf = (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")
        assert "acme-redirect:web" in conf
        assert "return 301 https://$host$request_uri;" in conf
        assert conf.index("acme_challenge.inc") < conf.index("return 301")
        assert "server_name web.test" in conf

    def test_tls_off_never_redirects(self) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "web", public_host="web.test", tls="off")
        gen = self.render_applied(edge=_EDGE)
        conf = (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")
        assert "return 301 https://" not in conf

    def test_contributor_skips_without_http(self) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "web", public_host="web.test", tls="acme")
        from raft.core.core.models.app import App
        from raft.core.core.models.manifest import AppSpec
        from raft.core.core.models.ports import PortSpec

        app = App(name="web", public_host="web.test", source="local", path="services/web/checkout")
        spec = AppSpec(
            ports=(PortSpec(name="http", container_port=80, expose="http"),),
            tls="acme",
        )
        d = self.tmp_path / "services" / "web" / "certs"
        d.mkdir(parents=True, exist_ok=True)
        (d / "acme.pem").write_text("pem\n", encoding="utf-8")
        (d / "acme.key").write_text("key\n", encoding="utf-8")
        empty = AcmeHttpRedirect().contribute(
            app, spec, edge=EdgeConfig(http=None, https=443), data_home=self.tmp_path
        )
        assert empty == []
