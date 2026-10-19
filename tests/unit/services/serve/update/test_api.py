"""ServeUpdateApi status + apply wiring."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.ops.update import UpdateCheckResult, UpdateOutcome
from raft.services.serve.update import ServeUpdateApi

from tests.unit.base import RaftTestCase


class TestServeUpdateApi(RaftTestCase):
    def test_status_ok(self) -> None:
        check = MagicMock()
        check.status.return_value = UpdateCheckResult(
            current="0.10.0",
            current_line="raft 0.10.0",
            latest_tag="v0.11.0",
            latest_version="0.11.0",
            update_available=True,
            release_url="https://example.test/releases/tag/v0.11.0",
            state="update_available",
            message="Update available: 0.10.0 → 0.11.0 (v0.11.0).",
        )
        client = self._client(check=check)
        res = client.get("/api/update/status")
        assert res.status_code == 200
        assert res.json()["updateAvailable"] is True
        assert res.json()["latestTag"] == "v0.11.0"

    def test_status_operator_error(self) -> None:
        check = MagicMock()
        check.status.side_effect = OperatorError("no release\nFix: retry")
        client = self._client(check=check)
        res = client.get("/api/update/status")
        assert res.status_code == 400
        assert "no release" in res.json()["detail"]

    def test_apply_runs_self_update(self) -> None:
        updater = MagicMock()
        updater.run.return_value = UpdateOutcome(
            already_current=False,
            before_line="raft 0.10.0",
            after_line="raft 0.11.0",
        )
        client = self._client(updater=updater)
        res = client.post("/api/update", json={})
        assert res.status_code == 200
        body = res.json()
        assert body["alreadyCurrent"] is False
        assert body["beforeLine"] == "raft 0.10.0"
        assert "raft render" in (body["nextSteps"] or "")
        updater.run.assert_called_once_with(ref=None, announce=False)

    def test_apply_passes_ref(self) -> None:
        updater = MagicMock()
        updater.run.return_value = UpdateOutcome(
            already_current=True, before_line="raft 0.11.0", after_line="raft 0.11.0"
        )
        client = self._client(updater=updater)
        res = client.post("/api/update", json={"ref": "main"})
        assert res.status_code == 200
        updater.run.assert_called_once_with(ref="main", announce=False)

    def test_apply_blank_ref_treated_as_unset(self) -> None:
        updater = MagicMock()
        updater.run.return_value = UpdateOutcome(
            already_current=True, before_line="raft 0.11.0", after_line="raft 0.11.0"
        )
        client = self._client(updater=updater)
        res = client.post("/api/update", json={"ref": "   "})
        assert res.status_code == 200
        updater.run.assert_called_once_with(ref=None, announce=False)

    def test_apply_missing_ref_key(self) -> None:
        updater = MagicMock()
        updater.run.return_value = UpdateOutcome(
            already_current=True, before_line="raft 0.11.0", after_line="raft 0.11.0"
        )
        client = self._client(updater=updater)
        res = client.post("/api/update", json={"confirm": True})
        assert res.status_code == 200
        updater.run.assert_called_once_with(ref=None, announce=False)

    def test_apply_operator_error(self) -> None:
        updater = MagicMock()
        updater.run.side_effect = OperatorError("install failed\nFix: retry")
        client = self._client(updater=updater)
        res = client.post("/api/update", json={})
        assert res.status_code == 400

    def _client(self, *, check=None, updater=None) -> TestClient:
        stack = Stack(root=self.tmp_path, apps=())
        app = FastAPI()
        ServeUpdateApi(stack, check=check, updater=updater).register(app)
        return TestClient(app)
