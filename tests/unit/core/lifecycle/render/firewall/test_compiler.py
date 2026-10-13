"""Firewall compiler: order, merge, deny/drop nginx mapping."""

from raft.core.lifecycle.render.firewall import FirewallCompiler, scope_name
from tests.unit.base import RaftTestCase
from tests.unit.services.serve.firewall.helpers import rule


class TestFirewallCompiler(RaftTestCase):
    def test_ordered_allow_deny_and_drop(self) -> None:
        rules = (
            rule("a", action="permit"),
            rule("b", action="drop", cidr="198.51.100.0/24"),
            rule("c", action="deny", cidr="203.0.113.0/24"),
        )
        compiler = FirewallCompiler()
        frag = compiler.compile_for(rules, port=80, service="any", scope="any_p80")
        assert frag.drop_cidrs == ("198.51.100.0/24",)
        text = compiler.location_text(frag)
        assert "return 444" in text and "allow 192.0.2.0/24;" in text
        assert "deny 203.0.113.0/24;" in text and "error_page 403" in text
        geo = compiler.geo_map_text(frag)
        assert "geo $remote_addr" in geo and "198.51.100.0/24 1;" in geo

    def test_merge_adjacent_same_action(self) -> None:
        rules = (
            rule("a", cidr="192.0.2.0/25", action="deny"),
            rule("b", cidr="192.0.2.128/25", action="deny"),
        )
        frag = FirewallCompiler().compile_for(rules, port=80, service="any", scope="x")
        assert len(frag.access) == 1
        assert frag.access[0].cidr == "192.0.2.0/24"

    def test_filters_port_service_protocol(self) -> None:
        rules = (
            rule("a", port=443, service="demo-api"),
            rule("b", protocol="udp"),
            rule("c", service="other"),
        )
        frag = FirewallCompiler().compile_for(
            rules, port=80, service="demo-api", scope="demo"
        )
        assert not frag.is_active()
        assert scope_name(service="demo-api", port=80) == "demo_api_p80"
