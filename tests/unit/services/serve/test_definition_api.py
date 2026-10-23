"""Serve ``/api/service/{name}/definition`` route tests."""

from raft.core.core.models.stack import Stack
from tests.unit.base import AppliedInventory, RaftTestCase
from . import fixtures as serve_fx


class TestServeDefinitionApi(RaftTestCase):
    def test_api_returns_yaml_for_app(self) -> None:
        stack = self._stack()
        client, _ = serve_fx.client_and_status(stack, serve_fx.empty_snapshot())
        res = client.get("/api/service/demo-api/definition")
        assert res.status_code == 200
        data = res.json()
        assert data["eligible"] is True
        assert data["app"] == "demo-api"
        assert data["path"] == "services/demo-api/app.yaml"
        assert "apiVersion: raft/v1" in data["yaml"]
        assert "demo-api" in data["yaml"]

    def test_api_404_unknown(self) -> None:
        stack = self._stack()
        client, _ = serve_fx.client_and_status(stack, serve_fx.empty_snapshot())
        res = client.get("/api/service/no-such/definition")
        assert res.status_code == 404

    def test_api_ineligible_gate(self) -> None:
        stack = self._stack()
        client, _ = serve_fx.client_and_status(stack, serve_fx.full_snapshot())
        res = client.get("/api/service/raft-gate/definition")
        assert res.status_code == 200
        data = res.json()
        assert data["eligible"] is False
        assert data["yaml"] is None

    def _stack(self) -> Stack:
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        return Stack.load_apps(self.tmp_path)
