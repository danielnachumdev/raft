"""Render emits gate ACL includes for default + Host servers."""

from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.models.acl_policy import AclPolicy
from raft.core.core.models.state.acl_store import AppAclStore
from raft.core.lifecycle.render.acl.nginx_text import AclNginxText
from tests.unit.base import AppliedInventory, RaftTestCase

_EDGE = EdgeConfig(http=80, https=None, streams=())


class TestAclRender(RaftTestCase):
    def test_nginx_whitelist_text(self) -> None:
        policy = AclPolicy.from_mapping(
            {
                "mode": "whitelist",
                "entries": [{"id": "lab", "cidr": "192.0.2.0/24"}],
            },
            path="t",
        )
        text = AclNginxText.location_rules(policy)
        assert "allow 192.0.2.0/24;" in text
        assert "deny all;" in text

    def test_gate_acl_in_default_server(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n"
            "acl:\n"
            "  gate:\n"
            "    mode: blacklist\n"
            "    entries:\n"
            "      - id: bad\n"
            "        cidr: 198.51.100.10\n",
            encoding="utf-8",
        )
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        gen = self.render_applied(edge=_EDGE)
        gate_inc = (gen / "nginx/gate-http/acl/_gate.inc").read_text(encoding="utf-8")
        assert "deny 198.51.100.10/32;" in gate_inc
        listeners = (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")
        assert "http-generated/acl/_gate.inc" in listeners

    def test_app_acl_emits_host_server(self) -> None:
        self._write_app_acl()
        gen = self.render_applied(edge=_EDGE)
        listeners = (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")
        assert "acl-host:demo-api" in listeners
        assert "http-generated/acl/demo-api.inc" in listeners
        app_inc = (gen / "nginx/gate-http/acl/demo-api.inc").read_text(encoding="utf-8")
        assert "allow 192.0.2.0/24;" in app_inc

    def _write_app_acl(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        AppAclStore(self.tmp_path).save(
            "demo-api",
            AclPolicy.from_mapping(
                {
                    "mode": "whitelist",
                    "entries": [{"id": "office", "cidr": "192.0.2.0/24"}],
                },
                path="app",
            ),
        )
