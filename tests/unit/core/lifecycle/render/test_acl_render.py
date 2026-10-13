"""ACL nginx text helpers + firewall-only render (legacy ACL includes cleared)."""

from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.models.acl_policy import AclPolicy
from raft.core.core.models.state.firewall_store import FirewallStore
from raft.core.lifecycle.render.acl.nginx_text import AclNginxText
from tests.unit.base import AppliedInventory, RaftTestCase
from tests.unit.services.serve.firewall.helpers import document, rule_dict

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

    def test_gate_firewall_in_default_server(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        FirewallStore(self.tmp_path).save(
            document(rule_dict("bad", cidr="198.51.100.10", action="deny"))
        )
        gen = self.render_applied(edge=_EDGE)
        gate_inc = (gen / "nginx/gate-http/firewall/any_p80.inc").read_text(
            encoding="utf-8"
        )
        assert "deny 198.51.100.10/32;" in gate_inc
        listeners = (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")
        assert "http-generated/firewall/any_p80.inc" in listeners
        assert not (gen / "nginx/gate-http/acl/_gate.inc").exists()

    def test_service_firewall_emits_host_server(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        FirewallStore(self.tmp_path).save(self._service_doc())
        gen = self.render_applied(edge=_EDGE)
        listeners = (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")
        assert "acl-host:demo-api" in listeners
        assert "http-generated/firewall/demo_api_p80.inc" in listeners
        app_inc = (gen / "nginx/gate-http/firewall/demo_api_p80.inc").read_text(
            encoding="utf-8"
        )
        assert "allow 192.0.2.0/24;" in app_inc

    @staticmethod
    def _service_doc():
        return document(
            rule_dict(
                "office",
                cidr="192.0.2.0/24",
                service="demo-api",
                action="permit",
            )
        )
