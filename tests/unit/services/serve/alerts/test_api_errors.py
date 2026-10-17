"""Serve Alerts API HTTP error statuses."""

from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.alerts.service.rules_service import RuleConflict
from raft.services.serve.alerts import ServeAlertsApi
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestServeAlertsApiErrors(RaftTestCase):
    def _client(self):
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True, exist_ok=True)
        stack = Stack(root=home, apps=())
        api = ServeAlertsApi(stack)
        app = FastAPI()
        api.register(app)
        return TestClient(app), api

    def test_not_found_and_conflict(self) -> None:
        client, api = self._client()
        assert client.get("/api/alerts/rules/missing").status_code == 404
        with patch.object(api._service, "create", side_effect=RuleConflict("dup")):
            assert client.post("/api/alerts/rules", json=RULE).status_code == 409

    def test_operator_error_on_create(self) -> None:
        client, api = self._client()
        with patch.object(api._service, "create", side_effect=OperatorError("bad\nFix")):
            assert client.post("/api/alerts/rules", json=RULE).status_code == 400
