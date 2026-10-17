"""More ServeAlertsApi handler coverage."""

from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.services.serve.alerts import ServeAlertsApi
from tests.unit.base import RaftTestCase

RULE = {
    "id": "demo-api-5xx-rate",
    "name": "demo",
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


class TestServeAlertsApiMore(RaftTestCase):
    def _setup(self):
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "settings.yaml").write_text(
            "notifications: {enabled: true, channels: []}\n", encoding="utf-8"
        )
        api = ServeAlertsApi(Stack(root=home, apps=()))
        app = FastAPI()
        api.register(app)
        return TestClient(app), api

    def test_list_export_enabled_replace(self) -> None:
        client, _api = self._setup()
        assert client.get("/api/alerts/rules").json()["rules"] == []
        client.post("/api/alerts/rules", json=RULE)
        assert "rules" in client.get("/api/alerts/export").json()
        assert (
            client.post(
                "/api/alerts/rules/demo-api-5xx-rate/enabled",
                json={"enabled": False},
            ).json()["enabled"]
            is False
        )
        assert (
            client.put("/api/alerts/rules/demo-api-5xx-rate", json=RULE).status_code
            == 200
        )

    def test_validate_document_and_operator_errors(self) -> None:
        client, api = self._setup()
        assert client.post(
            "/api/alerts/validate",
            json={"document": {"version": 1, "rules": [RULE]}},
        ).json()["ok"]
        with patch.object(
            api._service, "replace", side_effect=OperatorError("bad\nFix: x")
        ):
            client.post("/api/alerts/rules", json=RULE)
            assert (
                client.put("/api/alerts/rules/demo-api-5xx-rate", json=RULE).status_code
                == 400
            )
