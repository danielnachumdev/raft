"""Serve Alerts API TestClient coverage."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from raft.core.core.models.stack import Stack
from raft.services.serve.alerts import ServeAlertsApi
from tests.unit.base import RaftTestCase

RULE = {
    "id": "demo-api-5xx-rate",
    "name": "demo-api 5xx",
    "severity": "error",
    "for": "0s",
    "cooldown": "15m",
    "condition": {
        "signal": "metrics.http",
        "select": {"target": "demo-api", "metric": "error_rate_5xx"},
        "kind": "threshold",
        "params": {"aggregate": "avg", "window": "5m", "op": "gt", "value": 0.05},
    },
}


class TestServeAlertsApi(RaftTestCase):
    def _client(self) -> TestClient:
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "settings.yaml").write_text(
            "notifications:\n  enabled: true\n  channels: []\n",
            encoding="utf-8",
        )
        app = FastAPI()
        ServeAlertsApi(Stack(root=home, apps=())).register(app)
        return TestClient(app)

    def test_crud_validate_catalog_status(self) -> None:
        client = self._client()
        assert client.post("/api/alerts/rules", json=RULE).status_code == 200
        assert client.get("/api/alerts/rules/demo-api-5xx-rate").status_code == 200
        assert client.post("/api/alerts/validate", json={"rule": RULE}).json()["ok"]
        assert "sources" in client.get("/api/alerts/catalog").json()
        assert "enabled" in client.get("/api/alerts/status").json()
        assert client.delete("/api/alerts/rules/demo-api-5xx-rate").json()["ok"]
