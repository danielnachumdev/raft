"""Firewall includes on TLS + scaling Host servers."""

from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.models.state.firewall_store import FirewallStore
from raft.core.lifecycle.acme.paths import AcmePaths
from tests.unit.base import AppliedInventory, RaftTestCase
from tests.unit.core.lifecycle.firewall.helpers import document, rule_dict

_EDGE = EdgeConfig(http=80, https=443, streams=())
_SCALING = {
    "idleSeconds": 60,
    "wakeTimeoutSeconds": 120,
    "minUpSeconds": 30,
}


class TestAclTlsScalingRender(RaftTestCase):
    def test_scaling_host_includes_service_firewall(self) -> None:
        self._write_edge_settings()
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "demo-api",
            public_host="demo-api.test",
            extra={"scaling": _SCALING},
        )
        self._save_lab_firewall()
        conf = self._listeners()
        assert "http-generated/firewall/demo_api_p80.inc" in conf
        assert "scaling:demo-api" in conf

    def test_origin_tls_inlines_firewall(self) -> None:
        (self.tmp_path / "host" / "settings.yaml").write_text(
            "edge: {http: 80, https: 443}\n", encoding="utf-8"
        )
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test", tls="origin"
        )
        FirewallStore(self.tmp_path).save(
            document(
                rule_dict("bad", cidr="198.51.100.10", port=443, action="deny")
            )
        )
        self._write_origin_pems()
        tls = (
            self.render_applied(edge=_EDGE) / "nginx/gate-tls/demo-api.conf"
        ).read_text(encoding="utf-8")
        assert "http-generated/firewall/" in tls
        assert "proxy_router.inc" not in tls

    def test_acme_redirect_skips_plain_firewall_host(self) -> None:
        (self.tmp_path / "host" / "settings.yaml").write_text(
            "edge: {http: 80, https: 443}\n"
            "acme: {email: ops@example.com}\n",
            encoding="utf-8",
        )
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test", tls="acme"
        )
        self._save_lab_firewall()
        self._write_acme_pems()
        listeners = self._listeners()
        assert "acme-redirect:demo-api" in listeners
        assert "acl-host:demo-api" not in listeners
        assert "http-generated/firewall/demo_api_p80.inc" in listeners

    def _write_edge_settings(self) -> None:
        (self.tmp_path / "host" / "settings.yaml").write_text(
            "edge: {http: 80, https: 443}\n", encoding="utf-8"
        )

    def _save_lab_firewall(self) -> None:
        FirewallStore(self.tmp_path).save(
            document(
                rule_dict(
                    "lab",
                    cidr="192.0.2.0/24",
                    service="demo-api",
                    action="permit",
                )
            )
        )

    def _listeners(self) -> str:
        gen = self.render_applied(edge=_EDGE)
        return (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")

    def _write_origin_pems(self) -> None:
        certs = self.tmp_path / "services" / "demo-api" / "certs"
        certs.mkdir(parents=True, exist_ok=True)
        (certs / "origin.pem").write_text("pem", encoding="utf-8")
        (certs / "origin.key").write_text("key", encoding="utf-8")

    def _write_acme_pems(self) -> None:
        pem, key = AcmePaths(self.tmp_path).cert_files("demo-api")
        pem.parent.mkdir(parents=True, exist_ok=True)
        pem.write_text("pem", encoding="utf-8")
        key.write_text("key", encoding="utf-8")
