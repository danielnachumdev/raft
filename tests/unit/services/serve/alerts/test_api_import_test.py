"""Serve Alerts import, validate, test endpoints."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.notify.delivery_status import DeliveryStatus
from raft.services.serve.alerts import ServeAlertsApi
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestServeAlertsImportTest(RaftTestCase):
    def _client(self):
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        stack = Stack(root=home, apps=())
        api = ServeAlertsApi(stack)
        app = FastAPI()
        api.register(app)
        return TestClient(app), api

    def test_validate_and_test(self) -> None:
        client, _api = self._client()
        client.post("/api/alerts/rules", json=RULE)
        assert client.post("/api/alerts/validate", json={"document": {"version": 1, "rules": [RULE]}}).json()["ok"]
        ok = MagicMock()
        ok.channel_id = "ops"
        ok.type_id = "webhook"
        ok.result.status = DeliveryStatus.SUCCESS
        ok.result.error = None
        with patch("raft.services.serve.alerts.api.AlertTester") as Tester:
            Tester.return_value.send.return_value = []
            body = client.post("/api/alerts/rules/demo-api-5xx-rate/test").json()
            assert body["ok"] is False

    def test_import_error(self) -> None:
        client, api = self._client()
        with patch.object(api._service, "apply_document", side_effect=OperatorError("bad\nFix")):
            assert client.post("/api/alerts/import", json={"document": {"rules": []}}).status_code == 400
