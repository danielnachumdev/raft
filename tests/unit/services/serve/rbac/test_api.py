"""Serve RBAC API TestClient coverage (#307)."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import load_stack
from raft.core.observe.ops.status.models import StatusSnapshot
from raft.services.serve.http.app import ServeAppFactory
from raft.services.serve.http.paths import ServePaths
from raft.services.serve.rbac import ServeRbacApi
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.ops.status import fixtures as status_fx


class TestServeRbacApi(RaftTestCase):
    def test_get_put_catalog(self) -> None:
        client = self._client()
        empty = client.get("/api/rbac").json()
        assert empty["roles"] == []
        catalog = client.get("/api/rbac/catalog").json()
        assert "*:read" in catalog["permissions"]
        put = client.put(
            "/api/rbac",
            json={
                "version": 1,
                "roles": [{"id": "admin", "permissions": ["*:read", "*:write"]}],
                "bindings": [{"subject": "ops@example.com", "role": "admin"}],
            },
        )
        assert put.status_code == 200
        assert put.json()["document"]["roles"][0]["id"] == "admin"

    def test_put_operator_error(self) -> None:
        writer = MagicMock()
        writer.put.side_effect = OperatorError("bad rbac.\nFix: retry", has_fix=False)
        client = self._client(writer=writer)
        resp = client.put("/api/rbac", json={"version": 1})
        assert resp.status_code == 400
        assert "bad rbac" in resp.json()["detail"]

    def _client(self, writer=None) -> TestClient:
        ServePaths.spa_assets_dir().mkdir(parents=True, exist_ok=True)
        (self.tmp_path / "host" / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )
        stack = load_stack(self.tmp_path)
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=status_fx.empty_host_status(), containers=()
        )
        api = ServeRbacApi(stack, writer=writer)
        return TestClient(
            ServeAppFactory(stack, status=status, rbac=api).create()
        )
