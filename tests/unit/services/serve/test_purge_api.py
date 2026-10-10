"""Serve ``POST /api/purge`` route coverage."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from raft.errors.cta import OperatorError
from raft.services.ops.status.models import StatusSnapshot
from raft.services.serve.app import ServeAppFactory

from ...base import RaftTestCase, make_app, make_stack
from ...services.ops.status.fixtures import StatusFixtures


class TestServePurgeApi(RaftTestCase):
    def _client(self, actions) -> TestClient:
        stack = make_stack(self.tmp_path, (make_app("site"),))
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=StatusFixtures.empty_host_status(),
            containers=(),
        )
        return TestClient(
            ServeAppFactory(stack, status=status, actions=actions).create()
        )

    def test_api_purge_ok(self) -> None:
        actions = MagicMock()
        actions.purge.return_value = {
            "ok": True,
            "action": "purge",
            "reclaimed_bytes": 2048,
            "reclaimed_human": "2.0KiB",
            "images_bytes": 2048,
            "builder_bytes": 0,
        }
        response = self._client(actions).post("/api/purge")
        assert response.status_code == 200
        assert response.json()["reclaimed_human"] == "2.0KiB"
        actions.purge.assert_called_once_with()

    def test_api_purge_operator_error_is_400(self) -> None:
        actions = MagicMock()
        actions.purge.side_effect = OperatorError("failed to prune unused images")
        response = self._client(actions).post("/api/purge")
        assert response.status_code == 400
        assert "prune" in response.json()["detail"]
