"""Serve inbox API: list, summary, read/unread, dismiss."""

from typing import Optional
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import load_stack
from raft.core.observe.inbox import OperatorInboxService
from raft.core.observe.ops.status.models import StatusSnapshot
from raft.services.serve.http.app import ServeAppFactory
from raft.services.serve.http.paths import ServePaths
from raft.services.serve.inbox import ServeInboxApi
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.ops.status import fixtures as status_fx


class TestServeInboxApi(RaftTestCase):
    def _client(
        self, service: Optional[OperatorInboxService] = None
    ) -> TestClient:
        ServePaths.spa_assets_dir().mkdir(parents=True, exist_ok=True)
        (self.tmp_path / "host" / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )
        stack = load_stack(self.tmp_path)
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=status_fx.empty_host_status(), containers=()
        )
        api = ServeInboxApi(
            stack, service=service or OperatorInboxService(stack.root)
        )
        return TestClient(
            ServeAppFactory(stack, status=status, inbox=api).create()
        )

    def test_list_summary_mark_and_dismiss(self) -> None:
        client = self._client()
        listed = client.get("/api/inbox").json()
        assert listed["unreadCount"] >= 1
        assert listed["items"][0]["href"].endswith("#firewall-recommendations")
        self._assert_read_cycle(client, listed)
        item_id = listed["items"][0]["id"]
        all_read = client.post("/api/inbox/mark-all-read").json()
        assert all_read["unreadCount"] == 0
        dismissed = client.post(f"/api/inbox/items/{item_id}/dismiss").json()
        assert item_id not in {item["id"] for item in dismissed["items"]}

    def _assert_read_cycle(self, client: TestClient, listed: dict) -> None:
        summary = client.get("/api/inbox/summary").json()
        assert summary["unreadCount"] == listed["unreadCount"]
        assert summary["badgeSemantics"] == "unread"
        item_id = listed["items"][0]["id"]
        read = client.post(f"/api/inbox/items/{item_id}/read").json()
        assert read["unreadCount"] == listed["unreadCount"] - 1
        unread = client.post(f"/api/inbox/items/{item_id}/unread").json()
        assert unread["unreadCount"] == listed["unreadCount"]
        many = client.post("/api/inbox/read", json={"ids": [item_id]}).json()
        assert many["unreadCount"] == listed["unreadCount"] - 1
        client.post("/api/inbox/unread", json={"ids": [item_id]})

    def test_bad_body_and_dismiss_error(self) -> None:
        client = self._client()
        bad = client.post("/api/inbox/read", json={"ids": "nope"})
        assert bad.status_code == 400
        svc = MagicMock()
        svc.dismiss.side_effect = OperatorError("boom.\nFix: retry")
        err = self._client(service=svc).post(
            "/api/inbox/items/firewall-recommendation:x/dismiss"
        )
        assert err.status_code == 400
        assert "boom" in err.json()["detail"]
