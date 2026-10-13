"""Extra branch coverage for firewall policy includes and writers."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.acl_policy import AclPolicy
from raft.core.core.models.firewall import AclV1Migrator, FirewallDocument
from raft.core.core.models.stack import load_stack
from raft.core.core.models.state.acl_store import AppAclStore
from raft.core.core.models.state.firewall_store import FirewallStore
from raft.core.lifecycle.render.acl.effective import AclEffective
from raft.core.lifecycle.render.acl.inc_writer import AclIncWriter
from raft.core.lifecycle.render.firewall import (
    CompiledFragment,
    FirewallCompiler,
    FirewallEffective,
    FirewallIncWriter,
    PolicyIncludes,
)
from raft.core.lifecycle.render.firewall.compiler import scope_name
from raft.core.observe.ops.status.models import StatusSnapshot
from raft.services.serve.firewall.api import ServeFirewallApi
from raft.services.serve.firewall.apply import ServeFirewallService
from raft.services.serve.http.app import ServeAppFactory
from tests.unit.base import AppliedInventory, RaftTestCase
from tests.unit.core.observe.ops.status import fixtures as status_fx
from tests.unit.services.serve.firewall.helpers import document, rule, rule_dict


class TestFirewallCoverageExtra(RaftTestCase):
    def _settings(self, text: str = "edge: {http: 80, https: null}\n") -> None:
        (self.tmp_path / "settings.yaml").write_text(text, encoding="utf-8")

    def test_policy_includes_and_clear(self) -> None:
        self._settings()
        FirewallStore(self.tmp_path).save(document(rule_dict("svc", service="demo-api")))
        gate_http = self.tmp_path / "generated" / "nginx" / "gate-http"
        gate_http.mkdir(parents=True)
        policy = PolicyIncludes(
            self.tmp_path, EdgeConfig(http=80, https=None), gate_http
        )
        policy.write_all([])
        assert policy.needs_host_gate_server("demo-api")
        assert policy.host_include("demo-api", 80)
        self._clear_adopted(gate_http)

    def _clear_adopted(self, gate_http) -> None:
        FirewallStore(self.tmp_path).delete()
        maps = gate_http / "firewall-maps.conf"
        maps.write_text("# stale\n", encoding="utf-8")
        (gate_http / "firewall").mkdir(exist_ok=True)
        (gate_http / "firewall" / "stale.inc").write_text("x", encoding="utf-8")
        policy2 = PolicyIncludes(
            self.tmp_path, EdgeConfig(http=80, https=None), gate_http
        )
        policy2.write_all([])
        assert policy2.gate_include(80) == ""
        assert not maps.is_file()

    def test_compiler_collapse_misses(self) -> None:
        rules = (
            rule("a", action="deny"),
            rule("b", cidr="2001:db8::/32", action="deny"),
            rule("c", cidr="198.51.100.0/24", action="permit"),
        )
        frag = FirewallCompiler().compile_for(rules, port=80, service="any", scope="x")
        assert len(frag.access) == 3
        assert FirewallCompiler._collapse_cidrs("not-a-cidr", "192.0.2.0/24") is None
        assert (
            FirewallCompiler._collapse_cidrs("192.0.2.0/24", "198.51.100.0/24") is None
        )

    def test_migrate_skips_inactive_app_acl(self) -> None:
        self._settings("edge: {http: 80}\n")
        AppAclStore(self.tmp_path).save("demo-api", AclPolicy())
        path = AppAclStore(self.tmp_path).path_for("idle")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"mode": "off", "entries": []}\n', encoding="utf-8")
        assert AclV1Migrator(self.tmp_path, ports=()).migrate().rules == ()

    def test_document_rules_none_and_store_cleanup(self) -> None:
        doc = FirewallDocument.from_mapping({"version": 1, "rules": None}, path="fw")
        assert doc.rules == ()
        store = FirewallStore(self.tmp_path)
        store.save(FirewallDocument())
        with patch("os.path.exists", return_value=True), patch("os.unlink") as unlink:
            store.save(FirewallDocument())
            assert unlink.called

    def test_acl_clear_all_and_api_delete_error(self) -> None:
        self._settings("edge: {http: 80}\n")
        writer = AclIncWriter(
            self.tmp_path / "generated/nginx/gate-http", AclEffective(self.tmp_path)
        )
        writer.clear_all()
        writer._dir.mkdir(parents=True)
        (writer._dir / "x.inc").write_text("y", encoding="utf-8")
        writer.clear_all()
        assert list(writer._dir.glob("*.inc")) == []
        assert self._delete_client().delete("/api/firewall").status_code == 400

    def _delete_client(self) -> TestClient:
        stack = load_stack(self.tmp_path)
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=status_fx.empty_host_status(), containers=()
        )
        service = ServeFirewallService(stack, orchestrator=MagicMock())
        service._writer.clear = MagicMock(
            side_effect=OperatorError("boom\nFix: x", has_fix=False)
        )
        api = ServeFirewallApi(stack, service=service)
        return TestClient(ServeAppFactory(stack, status=status, firewall=api).create())

    def test_inc_writer_disk_include_and_forbidden(self) -> None:
        self._settings("edge: {http: 80, https: 443}\n")
        FirewallStore(self.tmp_path).save(
            document(rule_dict("d", port=443, action="drop"))
        )
        gate = self.tmp_path / "generated/nginx/gate-http"
        writer = FirewallIncWriter(
            gate, FirewallEffective(self.tmp_path), ports=(80, 443)
        )
        writer.write_all([])
        assert writer.needs_forbidden(service="any", port=443) is False
        assert "return 444" in (gate / "firewall" / "any_p443.inc").read_text(
            encoding="utf-8"
        )
        writer._fragments.clear()
        assert writer.gate_include(443) and writer.gate_include(80) == ""
        writer.clear_all()
        assert not (gate / "firewall-maps.conf").exists()

    def test_remaining_branches(self) -> None:
        self._settings("edge: {http: null, https: 443}\n")
        assert FirewallEffective(self.tmp_path)._edge_ports() == (443,)
        FirewallStore(self.tmp_path).delete()
        FirewallStore(self.tmp_path).save(document(rule_dict("p", port=443)))
        gate = self.tmp_path / "generated/nginx/gate-http"
        writer = FirewallIncWriter(gate, FirewallEffective(self.tmp_path), ports=(443,))
        self._exercise_writer(writer, gate)
        self._unsupported_service_excluded()

    def _exercise_writer(self, writer: FirewallIncWriter, gate) -> None:
        writer.write_all([])
        (gate / "firewall" / "stale.inc").write_text("old", encoding="utf-8")
        writer.write_all([])
        assert not (gate / "firewall" / "stale.inc").exists()
        scope = scope_name(service="any", port=443)
        writer._fragments[scope] = CompiledFragment(
            access=(), drop_cidrs=(), scope=scope
        )
        assert writer.gate_include(443) == ""
        writer._fragments.clear()
        maps = gate / "firewall-maps.conf"
        maps.write_text("geo {}\n", encoding="utf-8")
        writer._write_maps()
        assert not maps.exists()

    def _unsupported_service_excluded(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "worker",
            public_host="",
            extra={"ports": [], "readiness": {"type": "none"}},
        )
        svc = ServeFirewallService(load_stack(self.tmp_path), orchestrator=MagicMock())
        names = [s["name"] for s in svc.services()["services"]]
        assert "worker" not in names and "any" in names
