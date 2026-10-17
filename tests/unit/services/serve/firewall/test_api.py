"""Serve firewall API: save/import/export/recommendations with mocked render."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from raft.core.core.models.stack import load_stack
from raft.core.observe.ops.status.models import StatusSnapshot
from raft.services.serve.firewall.api import ServeFirewallApi
from raft.core.lifecycle.firewall import FirewallService
from raft.services.serve.http.app import ServeAppFactory
from tests.unit.base import AppliedInventory, RaftTestCase
from tests.unit.core.observe.ops.status import fixtures as status_fx
from tests.unit.core.lifecycle.firewall.helpers import rule_dict


class TestServeFirewallApi(RaftTestCase):
    def _client(self) -> TestClient:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
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

    def test_put_get_export_import(self) -> None:
        client = self._client()
        assert client.get("/api/firewall").json()["rules"] == []
        put = client.put("/api/firewall", json={"version": 1, "rules": [rule_dict()]})
        assert put.status_code == 200 and put.json()["applied"] is True
        self._orch.render.assert_called()
        self._assert_round_trip(client)

    def _assert_round_trip(self, client: TestClient) -> None:
        assert client.get("/api/firewall").json()["rules"][0]["cidr"] == "192.0.2.0/24"
        exported = client.get("/api/firewall/export").json()
        assert "source" not in exported and exported["rules"][0]["id"] == "lab"
        imported = client.post(
            "/api/firewall/import",
            json={"version": 1, "rules": [rule_dict("lab2", action="deny")]},
        )
        assert imported.json()["rules"][0]["action"] == "deny"
        services = client.get("/api/firewall/services").json()["services"]
        assert services[0]["name"] == "any"
        assert any(s["name"] == "demo-api" for s in services)

    def test_put_validation_error(self) -> None:
        client = self._client()
        bad = client.put("/api/firewall", json={"rules": [rule_dict(action="nope")]})
        assert bad.status_code == 400
        assert "deny, permit, or drop" in bad.json()["detail"]

    def test_import_port_any_and_recommendations(self) -> None:
        client = self._client()
        bad = client.post("/api/firewall/import", json={"rules": [rule_dict(port=-1)]})
        assert bad.status_code == 400
        ok = client.post(
            "/api/firewall/import",
            json={
                "version": 1,
                "rules": [rule_dict("anyport", port="any", action="deny")],
            },
        )
        assert ok.status_code == 200 and ok.json()["rules"][0]["port"] == "any"
        self._assert_recommendations(client)

    def _assert_recommendations(self, client: TestClient) -> None:
        recs = client.get("/api/firewall/recommendations").json()["recommendations"]
        ids = {item["id"] for item in recs}
        assert "permit-port-80" in ids
        assert "default-deny" in ids
        dismissed = client.post(
            "/api/firewall/recommendations/permit-port-80/dismiss"
        ).json()["recommendations"]
        assert all(item["id"] != "permit-port-80" for item in dismissed)
