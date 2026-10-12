"""ACL includes on TLS + scaling Host servers."""

from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.models.acl_policy import AclPolicy
from raft.core.core.models.state.acl_store import AppAclStore
from raft.core.lifecycle.acme.paths import AcmePaths
from tests.unit.base import AppliedInventory, RaftTestCase

_EDGE = EdgeConfig(http=80, https=443, streams=())
_SCALING = {
    "idleSeconds": 60,
    "wakeTimeoutSeconds": 120,
    "minUpSeconds": 30,
}


class TestAclTlsScalingRender(RaftTestCase):
    def test_scaling_host_includes_app_acl(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: 443}\n", encoding="utf-8"
        )
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "demo-api",
            public_host="demo-api.test",
            extra={"scaling": _SCALING},
        )
        AppAclStore(self.tmp_path).save(
            "demo-api",
            AclPolicy.from_mapping(
                {
                    "mode": "whitelist",
                    "entries": [{"id": "lab", "cidr": "192.0.2.0/24"}],
                },
                path="app",
            ),
        )
        gen = self.render_applied(edge=_EDGE)
        conf = (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")
        assert "http-generated/acl/demo-api.inc" in conf
        assert "scaling:demo-api" in conf

    def test_origin_tls_inlines_acl(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: 443}\n"
            "acl:\n"
            "  gate:\n"
            "    mode: blacklist\n"
            "    entries:\n"
            "      - id: bad\n"
            "        cidr: 198.51.100.10\n",
            encoding="utf-8",
        )
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "demo-api",
            public_host="demo-api.test",
            tls="origin",
        )
        certs = self.tmp_path / "certs" / "demo-api"
        certs.mkdir(parents=True)
        (certs / "origin.pem").write_text("pem", encoding="utf-8")
        (certs / "origin.key").write_text("key", encoding="utf-8")
        gen = self.render_applied(edge=_EDGE)
        tls = (gen / "nginx/gate-tls/demo-api.conf").read_text(encoding="utf-8")
        assert "http-generated/acl/demo-api.inc" in tls
        assert "proxy_router.inc" not in tls

    def test_acme_redirect_skips_plain_acl_host(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: 443}\n"
            "acme: {email: ops@example.com}\n",
            encoding="utf-8",
        )
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "demo-api",
            public_host="demo-api.test",
            tls="acme",
        )
        AppAclStore(self.tmp_path).save(
            "demo-api",
            AclPolicy.from_mapping(
                {
                    "mode": "whitelist",
                    "entries": [{"id": "lab", "cidr": "192.0.2.0/24"}],
                },
                path="app",
            ),
        )
        pem, key = AcmePaths(self.tmp_path).cert_files("demo-api")
        pem.parent.mkdir(parents=True, exist_ok=True)
        pem.write_text("pem", encoding="utf-8")
        key.write_text("key", encoding="utf-8")
        gen = self.render_applied(edge=_EDGE)
        listeners = (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")
        assert "acme-redirect:demo-api" in listeners
        assert "acl-host:demo-api" not in listeners
        assert "http-generated/acl/demo-api.inc" in listeners
