"""Serve ``/api/metrics/http`` route smoke tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from raft.controller.http_metrics import HTTP_METRICS_FILENAME
from raft.controller.metrics import METRICS_DIR

from tests.unit.base import RaftTestCase, make_stack
from .test_app import _ServeFixtures


class TestServeHttpMetricsApi(RaftTestCase):
    def test_api_metrics_http_reads_jsonl(self) -> None:
        stack = make_stack(self.tmp_path)
        ts = datetime.now(timezone.utc).isoformat()
        self._write_sample(stack, ts=ts)
        client, _ = _ServeFixtures.client_and_status(
            stack, _ServeFixtures.empty_snapshot()
        )
        data = client.get("/api/metrics/http", params={"window": 3600}).json()
        assert data["kind"] == "http" and data["cursor"] == ts
        assert {s["id"] for s in data["series"]} == {"edge"}

    def test_api_metrics_http_rejects_bad_start(self) -> None:
        client, _ = _ServeFixtures.client_and_status(
            make_stack(self.tmp_path), _ServeFixtures.empty_snapshot()
        )
        res = client.get("/api/metrics/http", params={"start": "not-a-time"})
        assert res.status_code == 400

    @staticmethod
    def _write_sample(stack, *, ts: str) -> None:
        path = stack.root / METRICS_DIR / HTTP_METRICS_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": ts,
            "requests": 2,
            "rps": 2.0,
            "in_flight": 1,
            "duration_ms": {"avg": 5, "p50": 5, "p95": 5, "p99": 5},
            "status_class": {"2xx": 2, "3xx": 0, "4xx": 0, "5xx": 0, "other": 0},
            "by_service": {},
        }
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
