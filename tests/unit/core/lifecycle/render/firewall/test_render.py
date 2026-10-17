"""Adopted firewall document compiles into gate includes (reload-class)."""

from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.models.state.firewall_store import FirewallStore
from tests.unit.base import AppliedInventory, RaftTestCase
from tests.unit.core.lifecycle.firewall.helpers import document, rule_dict

_EDGE = EdgeConfig(http=80, https=None, streams=())


class TestFirewallRender(RaftTestCase):
    def test_adopted_firewall_on_default_server(self) -> None:
        self._prep()
        FirewallStore(self.tmp_path).save(document(rule_dict("lab", action="deny")))
        gen = self.render_applied(edge=_EDGE)
        inc = (gen / "nginx/gate-http/firewall/any_p80.inc").read_text(encoding="utf-8")
        assert "deny 192.0.2.0/24;" in inc
        listeners = (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")
        assert "http-generated/firewall/any_p80.inc" in listeners

    def test_service_rule_emits_host_server(self) -> None:
        self._prep()
        FirewallStore(self.tmp_path).save(
            document(rule_dict("svc", cidr="198.51.100.10", service="demo-api", action="drop"))
        )
        gen = self.render_applied(edge=_EDGE)
        listeners = (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")
        assert "acl-host:demo-api" in listeners
        assert "firewall/demo_api_p80.inc" in listeners
        maps = (gen / "nginx/gate-http/firewall-maps.conf").read_text(encoding="utf-8")
        assert "198.51.100.10/32 1;" in maps

    def _prep(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
