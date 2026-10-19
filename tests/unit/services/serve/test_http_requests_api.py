"""Serve ``/api/service/{name}/http-requests`` route tests."""

from pathlib import Path

from raft.core.core.models.stack import Stack
from raft.core.core.models.state.scaling_store import ScalingStore
from raft.services.controller.jobs.metrics.http_scrape import (
    ACCESS_LOG_NAME,
    GATE_HTTP_LOG_DIR,
)

from tests.unit.base import AppliedInventory, RaftTestCase
from . import fixtures as serve_fx


class TestServeHttpRequestsApi(RaftTestCase):
    def test_api_returns_rows_for_host_app(self) -> None:
        stack = self._stack()
        self._write_log(
            stack.root,
            '0.01 200 demo-api.test 2026-10-13T01:00:00+00:00 GET /health '
            '192.0.2.10 "DemoAgent/1.0"\n',
        )
        client, _ = serve_fx.client_and_status(stack, serve_fx.empty_snapshot())
        res = client.get("/api/service/demo-api/http-requests", params={"limit": 50})
        assert res.status_code == 200
        data = res.json()
        assert data["eligible"] is True
        assert data["requests"][0]["path"] == "/health"
        assert data["requests"][0]["client_ip"] == "192.0.2.10"

    def test_api_scaled_to_zero_still_returns_history(self) -> None:
        stack = self._stack()
        ScalingStore(stack.root).mark_scaled_to_zero("demo-api")
        self._write_log(
            stack.root,
            '0.01 200 demo-api.test 2026-10-13T01:00:00+00:00 GET /past '
            '192.0.2.10 "DemoAgent/1.0"\n',
        )
        client, _ = serve_fx.client_and_status(stack, serve_fx.empty_snapshot())
        res = client.get("/api/service/demo-api/http-requests")
        assert res.status_code == 200
        data = res.json()
        assert data["eligible"] is True
        assert data["scaled_to_zero"] is True
        assert data["requests"][0]["path"] == "/past"

    def test_api_404_unknown(self) -> None:
        stack = self._stack()
        client, _ = serve_fx.client_and_status(stack, serve_fx.empty_snapshot())
        res = client.get("/api/service/no-such/http-requests")
        assert res.status_code == 404

    def test_api_ineligible_gate(self) -> None:
        stack = self._stack()
        client, _ = serve_fx.client_and_status(stack, serve_fx.full_snapshot())
        res = client.get("/api/service/raft-gate/http-requests")
        assert res.status_code == 200
        assert res.json()["eligible"] is False

    def test_api_clamps_limit_low_and_high(self) -> None:
        stack = self._stack()
        client, _ = serve_fx.client_and_status(stack, serve_fx.empty_snapshot())
        low = client.get(
            "/api/service/demo-api/http-requests", params={"limit": 0}
        ).json()
        high = client.get(
            "/api/service/demo-api/http-requests", params={"limit": 9999}
        ).json()
        assert low["limit"] == 1
        assert high["limit"] == 500

    def _stack(self) -> Stack:
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        return Stack.load_apps(self.tmp_path)

    @staticmethod
    def _write_log(root: Path, body: str) -> None:
        path = root / GATE_HTTP_LOG_DIR / ACCESS_LOG_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
