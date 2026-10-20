"""Serve Alerts API exception handlers."""
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.services.serve.alerts import ServeAlertsApi
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE

class TestServeAlertsApiHandlers(RaftTestCase):
    def _client(self):
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        stack = Stack(root=home, apps=[])
        api = ServeAlertsApi(stack)
        app = FastAPI()
        api.register(app)
        return TestClient(app), api

    def test_replace_and_enabled_missing(self) -> None:
        c, api = self._client()
        with patch.object(api._service, "replace", side_effect=KeyError("x")):
            assert c.put("/api/alerts/rules/x", json=RULE).status_code == 404
        with patch.object(api._service, "set_enabled", side_effect=KeyError("x")):
            assert c.post("/api/alerts/rules/x/enabled", json={"enabled": True}).status_code == 404

    def test_delete_and_dry_run(self) -> None:
        c, api = self._client()
        with patch.object(api._service, "delete", side_effect=OperatorError("bad\nFix")):
            assert c.delete("/api/alerts/rules/x").status_code == 400
        assert c.post("/api/alerts/dry-run", json={"ruleId": "missing"}).status_code == 404
        assert c.post("/api/alerts/validate", json={"document": {"version": 1, "rules": []}}).json()["ok"]

    def test_catalog_with_apps(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        stack = Stack(root=home, apps=[type("A", (), {"name": "demo-api"})()])
        app = FastAPI()
        ServeAlertsApi(stack).register(app)
        body = TestClient(app).get("/api/alerts/catalog").json()
        assert "demo-api" in str(body)
