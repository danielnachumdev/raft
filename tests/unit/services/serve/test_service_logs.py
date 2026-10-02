"""Unit tests for serve ``GET /api/service/{name}/logs``."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from raft.errors import OperatorError
from raft.services.ops.status.models import StatusSnapshot
from raft.services.serve.app import ServeAppFactory

from ...base import RaftTestCase, make_app, make_stack
from ...services.ops.status.fixtures import StatusFixtures


class TestServeServiceLogs(RaftTestCase):
    def _client(self, logs) -> TestClient:
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=StatusFixtures.empty_host_status(),
            containers=(),
        )
        stack = make_stack(self.tmp_path, (make_app("site"),))
        return TestClient(
            ServeAppFactory(stack, status=status, logs=logs).create()
        )

    def test_api_service_logs_returns_text(self) -> None:
        logs = MagicMock()
        logs.snapshot.return_value = "line1\nline2"
        response = self._client(logs).get("/api/service/site/logs", params={"tail": 20})
        assert response.status_code == 200
        data = response.json()
        assert data == {"service": "site", "tail": 20, "text": "line1\nline2"}
        logs.snapshot.assert_called_once_with("site", tail=20)

    def test_api_service_logs_default_tail(self) -> None:
        logs = MagicMock()
        logs.snapshot.return_value = ""
        response = self._client(logs).get("/api/service/raft-gate/logs")
        assert response.status_code == 200
        assert response.json()["tail"] == 100
        logs.snapshot.assert_called_once_with("raft-gate", tail=100)

    def test_api_service_logs_clamps_tail(self) -> None:
        logs = MagicMock()
        logs.snapshot.return_value = "ok"
        client = self._client(logs)
        low = client.get("/api/service/site/logs", params={"tail": 0})
        high = client.get("/api/service/site/logs", params={"tail": 99999})
        assert low.json()["tail"] == 1
        assert high.json()["tail"] == 5000
        assert logs.snapshot.call_args_list[0].kwargs["tail"] == 1
        assert logs.snapshot.call_args_list[1].kwargs["tail"] == 5000

    def test_api_service_logs_unknown_is_404(self) -> None:
        logs = MagicMock()
        logs.snapshot.side_effect = OperatorError(
            "unknown logs target 'missing' (known: gate)",
        )
        response = self._client(logs).get("/api/service/missing/logs")
        assert response.status_code == 404
        assert "missing" in response.json()["detail"]

    def test_api_service_logs_not_running_is_400(self) -> None:
        logs = MagicMock()
        logs.snapshot.side_effect = OperatorError(
            "service 'site' is not running — bring the stack up first",
            has_fix=False,
        )
        response = self._client(logs).get("/api/service/site/logs")
        assert response.status_code == 400
        assert "not running" in response.json()["detail"]
