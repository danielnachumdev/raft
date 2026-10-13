"""Serve ACL API: gate + app CRUD with mocked render/reload."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from raft.core.core.models.stack import load_stack
from raft.core.observe.ops.status.models import StatusSnapshot
from raft.services.serve.acl.api import ServeAclApi
from raft.services.serve.acl.apply import ServeAclService
from raft.services.serve.http.app import ServeAppFactory
from tests.unit.base import AppliedInventory, RaftTestCase
from tests.unit.core.observe.ops.status import fixtures as status_fx


class TestServeAclApi(RaftTestCase):
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
        service = ServeAclService(stack, orchestrator=orch)
        api = ServeAclApi(stack, service=service)
        client = TestClient(ServeAppFactory(stack, status=status, acl=api).create())
        self._orch = orch
        return client

    def test_gate_put_get_delete(self) -> None:
        client = self._client()
        assert client.get("/api/acl/gate").json() == {"mode": "off", "entries": []}
        put = client.put(
            "/api/acl/gate",
            json={
                "mode": "whitelist",
                "entries": [{"id": "lab", "cidr": "192.0.2.0/24"}],
            },
        )
        assert put.status_code == 200
        body = put.json()
        assert body["mode"] == "whitelist"
        assert body["applied"] is True
        self._orch.render.assert_called()
        assert client.get("/api/acl/gate").json()["entries"][0]["cidr"] == "192.0.2.0/24"
        cleared = client.delete("/api/acl/gate")
        assert cleared.json()["mode"] == "off"

    def test_app_acl_happy_path(self) -> None:
        client = self._client()
        meta = client.get("/api/acl/apps/demo-api/meta").json()
        assert meta["supported"] is True
        put = client.put(
            "/api/acl/apps/demo-api",
            json={
                "mode": "blacklist",
                "entries": [{"id": "bad", "cidr": "198.51.100.10"}],
            },
        )
        assert put.status_code == 200
        assert put.json()["mode"] == "blacklist"
        assert client.get("/api/acl/apps/demo-api").json()["entries"][0]["id"] == "bad"
        assert client.delete("/api/acl/apps/demo-api").json()["mode"] == "off"

    def test_worker_app_rejected(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "worker",
            public_host="",
            extra={"ports": [], "readiness": {"type": "none"}},
        )
        client = self._client()
        meta = client.get("/api/acl/apps/worker/meta").json()
        assert meta["supported"] is False
        bad = client.put(
            "/api/acl/apps/worker",
            json={
                "mode": "whitelist",
                "entries": [{"id": "lab", "cidr": "192.0.2.0/24"}],
            },
        )
        assert bad.status_code == 400
        assert "expose: http" in bad.json()["detail"]
