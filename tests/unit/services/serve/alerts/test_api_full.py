"""Serve Alerts API happy paths."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from raft.core.core.models.stack import Stack
from raft.services.serve.alerts import ServeAlertsApi
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE

class TestServeAlertsApiFull(RaftTestCase):
    def _client(self):
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        stack = Stack(root=home, apps=[])
        app = FastAPI()
        ServeAlertsApi(stack).register(app)
        return TestClient(app)

    def test_replace_enabled_import(self) -> None:
        c = self._client()
        c.post("/api/alerts/rules", json=RULE)
        assert c.put("/api/alerts/rules/demo-api-5xx-rate", json={**RULE, "name": "x"}).status_code == 200
        assert c.post("/api/alerts/rules/demo-api-5xx-rate/enabled", json={"enabled": False}).status_code == 200
        assert c.post("/api/alerts/import", json={"document": {"version": 1, "rules": [RULE]}}).status_code == 200
        assert c.post("/api/alerts/dry-run", json={"rule": RULE}).status_code == 200
