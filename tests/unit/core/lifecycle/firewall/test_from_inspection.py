"""Inspection → ordered firewall merge/API (#198); dummy data only."""

import pytest
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import load_stack
from raft.core.observe.ops.status.models import StatusSnapshot
from raft.services.serve.firewall.api import ServeFirewallApi
from raft.core.lifecycle.firewall import FirewallService
from raft.core.lifecycle.firewall.from_inspection import InspectionFirewall
from raft.services.serve.http.app import ServeAppFactory
from tests.unit.base import AppliedInventory, RaftTestCase
from tests.unit.core.observe.ops.status import fixtures as status_fx
from tests.unit.core.lifecycle.firewall.helpers import document, rule, rule_dict


class TestInspectionFirewall(RaftTestCase):
    def _stack(self, *, edge: str = "edge: {http: 80, https: 443}\n"):
        (self.tmp_path / "settings.yaml").write_text(edge, encoding="utf-8")
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        return load_stack(self.tmp_path)

    def _put_rules(self, stack, *rules: dict) -> None:
        FirewallService(stack, orchestrator=MagicMock()).put(
            {"version": 1, "rules": list(rules)}
        )

    def test_host_cidr_and_prepend(self) -> None:
        fw = InspectionFirewall(self._stack())
        assert fw.host_cidr("192.0.2.10") == "192.0.2.10/32"
        assert fw.host_cidr("2001:db8::1") == "2001:db8::1/128"
        base = document(rule_dict("permit-any", cidr="0.0.0.0/0", action="permit"))
        draft = fw.draft(client_ip="192.0.2.10", service="demo-api", action="deny")
        assert draft["insert"] == "prepend"
        assert draft["rule"]["cidr"] == "192.0.2.10/32"
        assert draft["rule"]["service"] == "demo-api"
        assert draft["rule"]["port"] == 443
        merged = fw.prepend(base, rule(**draft["rule"]))
        assert merged.rules[0].id.startswith("inspect-demo-api-")
        assert merged.rules[1].id == "permit-any"

    def test_remove_by_id_and_edge_ports(self) -> None:
        stack = self._stack(edge="edge: {http: 80, https: null}\n")
        fw = InspectionFirewall(stack)
        self._put_rules(
            stack,
            rule_dict("keep", cidr="198.51.100.0/24"),
            rule_dict("hit", cidr="192.0.2.10/32", action="deny"),
        )
        draft = fw.draft(client_ip="192.0.2.10", service="any")
        assert draft["rule"]["port"] == 80 and draft["rule"]["service"] == "any"
        by_id = fw.remove_for_client(client_ip="192.0.2.10", rule_id="hit")
        assert [r.id for r in by_id.rules] == ["keep"]
        self._put_rules(stack, *[r.to_public() for r in by_id.rules])
        with pytest.raises(OperatorError, match="No firewall rule matches"):
            fw.remove_for_client(client_ip="192.0.2.10")

    def test_compose_id_service_and_empty_edge(self) -> None:
        stack = self._stack(edge="edge: {http: null, https: null}\n")
        fw = InspectionFirewall(stack)
        draft = fw.draft(client_ip="192.0.2.10", service=stack.apps[0].compose_id)
        assert draft["rule"]["service"] == "demo-api"
        assert draft["rule"]["port"] == "any"
        with pytest.raises(OperatorError, match="not an applied Host-routed"):
            fw.draft(client_ip="192.0.2.10", service="missing-app")


class TestInspectionFirewallApi(RaftTestCase):
    def _client(self) -> TestClient:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: 443}\n", encoding="utf-8"
        )
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        stack = load_stack(self.tmp_path)
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=status_fx.empty_host_status(), containers=()
        )
        orch = MagicMock()
        api = ServeFirewallApi(
            stack, service=FirewallService(stack, orchestrator=orch)
        )
        self._orch = orch
        return TestClient(ServeAppFactory(stack, status=status, firewall=api).create())

    def test_draft_apply_remove(self) -> None:
        client = self._client()
        self._seed_broad(client)
        body = self._draft(client)
        rules = self._apply_deny(client, body)
        assert rules[0]["cidr"] == "192.0.2.10/32"
        assert rules[0]["action"] == "deny"
        assert rules[1]["id"] == "broad"
        removed = client.post(
            "/api/firewall/from-inspection/remove",
            json={"client_ip": "192.0.2.10"},
        )
        assert removed.status_code == 200
        assert [r["id"] for r in removed.json()["rules"]] == ["broad"]
        self._orch.render.assert_called()

    def test_api_errors(self) -> None:
        client = self._client()
        bad = client.get(
            "/api/firewall/from-inspection",
            params={"client_ip": "not-an-ip"},
        )
        assert bad.status_code == 400
        bad_apply = client.post(
            "/api/firewall/from-inspection",
            json={"rule": rule_dict(action="nope")},
        )
        assert bad_apply.status_code == 400
        bad_rm = client.post(
            "/api/firewall/from-inspection/remove",
            json={"client_ip": "192.0.2.10"},
        )
        assert bad_rm.status_code == 400

    @staticmethod
    def _seed_broad(client: TestClient) -> None:
        client.put(
            "/api/firewall",
            json={
                "version": 1,
                "rules": [rule_dict("broad", cidr="0.0.0.0/0", action="permit")],
            },
        )

    @staticmethod
    def _draft(client: TestClient) -> dict:
        draft = client.get(
            "/api/firewall/from-inspection",
            params={"client_ip": "192.0.2.10", "service": "demo-api"},
        )
        assert draft.status_code == 200
        return draft.json()

    @staticmethod
    def _apply_deny(client: TestClient, body: dict) -> list:
        applied = client.post(
            "/api/firewall/from-inspection",
            json={"rule": {**body["rule"], "action": "deny"}},
        )
        assert applied.status_code == 200
        return applied.json()["rules"]
