"""Branch coverage for firewall store, writer, and effective migration."""

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.firewall import FirewallDocument, FirewallRule
from raft.core.core.models.state.firewall_store import FirewallStore
from raft.core.lifecycle.render.firewall import FirewallCompiler, FirewallEffective
from raft.core.lifecycle.render.firewall.compiler import CompiledFragment
from raft.core.lifecycle.firewall.store_write import FirewallDocumentWriter
from tests.unit.base import RaftTestCase
from tests.unit.core.lifecycle.firewall.helpers import document, rule_dict


class TestFirewallCoverage(RaftTestCase):
    def test_store_round_trip_and_delete(self) -> None:
        store = FirewallStore(self.tmp_path)
        assert store.load() is None
        store.save(document(rule_dict("x", port=443, action="drop", cidr="192.0.2.1")))
        assert store.exists() and store.load() is not None
        store.delete()
        assert not store.exists()

    def test_effective_migrates_when_absent(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n"
            "acl:\n  gate:\n    mode: blacklist\n"
            "    entries:\n      - id: bad\n        cidr: 198.51.100.10\n",
            encoding="utf-8",
        )
        eff = FirewallEffective(self.tmp_path)
        assert not eff.adopted and eff.is_active()
        assert eff.document.source == "acl-v1-migrated"

    def test_writer_and_compiler_edges(self) -> None:
        writer = FirewallDocumentWriter(self.tmp_path)
        assert not writer.adopted()
        public = writer.put({"rules": [rule_dict("a")]})
        assert public["source"] == "firewall" and writer.adopted()
        writer.clear()
        empty = FirewallCompiler().compile_for((), port=80, service="any", scope="x")
        assert FirewallCompiler().location_text(empty) == ""
        assert FirewallCompiler().geo_map_text(empty) == ""
        assert FirewallCompiler.forbidden_location()
        assert not CompiledFragment(access=(), drop_cidrs=(), scope="x").is_active()

    def test_store_corrupt_yaml(self) -> None:
        path = self.tmp_path / "state" / "firewall" / "rules.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(":\n  - bad", encoding="utf-8")
        try:
            FirewallStore(self.tmp_path).load()
            raise AssertionError("expected OperatorError")
        except OperatorError as exc:
            assert "cannot read" in str(exc)

    def test_rule_validation_edges(self) -> None:
        any_rule = FirewallRule.from_mapping(rule_dict(port="any"), path="r")
        assert any_rule.is_port_any() and any_rule.applies_to_port(443)
        assert any_rule.to_public()["port"] == "any"
        zero = FirewallRule.from_mapping(rule_dict(port=0), path="r")
        assert zero.is_port_any()
        for raw in (
            None,
            rule_dict(id=""),
            rule_dict(port=-1),
            rule_dict(port="x"),
            rule_dict(protocol=""),
            rule_dict(service=""),
        ):
            try:
                FirewallRule.from_mapping(raw, path="r")
                raise AssertionError(f"expected error for {raw!r}")
            except OperatorError:
                pass
        assert FirewallDocument() is not None
