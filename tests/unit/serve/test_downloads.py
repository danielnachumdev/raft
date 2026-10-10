"""Serve catalog + logs/metrics download endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from raft.controller.metrics import METRICS_DIR, METRICS_FILENAME
from raft.errors.cta import OperatorError
from raft.ops.status.models import StatusSnapshot
from raft.serve.app import ServeAppFactory
from raft.serve.downloads import ServeDownloads

from tests.unit.base import RaftTestCase, make_app, make_stack
from tests.unit.ops.status.fixtures import StatusFixtures


class TestServeDownloads(RaftTestCase):
    def _client(self, logs=None) -> TestClient:
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=StatusFixtures.empty_host_status(),
            containers=(),
        )
        stack = make_stack(self.tmp_path, (make_app("site"),))
        return TestClient(
            ServeAppFactory(stack, status=status, logs=logs).create()
        )

    def test_export_catalog_lists_shipped_formats(self) -> None:
        data = self._client(MagicMock()).get("/api/exports").json()
        assert [row["id"] for row in data["logs"]] == ["txt", "json"]
        assert [row["id"] for row in data["metrics"]] == ["csv"]

    def test_logs_download_txt_attachment(self) -> None:
        logs = MagicMock()
        logs.snapshot.return_value = "hello\n"
        response = self._client(logs).get(
            "/api/service/site/logs/download", params={"format": "txt", "tail": 20}
        )
        assert response.status_code == 200
        assert response.content == b"hello\n"
        assert "text/plain" in response.headers["content-type"]
        assert "raft-logs-site.txt" in response.headers["content-disposition"]
        logs.snapshot.assert_called_once_with("site", tail=20)

    def test_logs_download_json_lines(self) -> None:
        logs = MagicMock()
        logs.snapshot.return_value = "a\nb"
        response = self._client(logs).get(
            "/api/service/site/logs/download", params={"format": "json"}
        )
        data = json.loads(response.content)
        assert data["lines"] == ["a", "b"]
        assert "raft-logs-site.json" in response.headers["content-disposition"]

    def test_logs_download_unknown_format_is_400(self) -> None:
        logs = MagicMock()
        response = self._client(logs).get(
            "/api/service/site/logs/download", params={"format": "xlsx"}
        )
        assert response.status_code == 400
        assert "xlsx" in response.json()["detail"]
        logs.snapshot.assert_not_called()

    def test_logs_download_unknown_service_is_404(self) -> None:
        logs = MagicMock()
        logs.snapshot.side_effect = OperatorError(
            "unknown logs target 'missing' (known: gate)",
        )
        response = self._client(logs).get("/api/service/missing/logs/download")
        assert response.status_code == 404

    def test_logs_download_clamps_tail(self) -> None:
        logs = MagicMock()
        logs.snapshot.return_value = "x"
        client = self._client(logs)
        client.get("/api/service/site/logs/download", params={"tail": 0})
        client.get("/api/service/site/logs/download", params={"tail": 99999})
        assert logs.snapshot.call_args_list[0].kwargs["tail"] == 1
        assert logs.snapshot.call_args_list[1].kwargs["tail"] == 5000

    def test_metrics_download_csv(self) -> None:
        stack = make_stack(self.tmp_path)
        ts = datetime.now(timezone.utc).isoformat()
        self._write_sample(stack, ts=ts)
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=StatusFixtures.empty_host_status(), containers=()
        )
        client = TestClient(ServeAppFactory(stack, status=status).create())
        response = client.get("/api/metrics/download", params={"format": "csv"})
        assert response.status_code == 200
        text = response.content.decode("utf-8")
        assert text.startswith("t,series_id,")
        assert "raft-gate" in text
        assert "raft-metrics.csv" in response.headers["content-disposition"]

    def test_split_services_ignores_blank_tokens(self) -> None:
        assert ServeDownloads._split_services(" , , ") is None
        assert ServeDownloads._split_services("gate, site") == ["gate", "site"]

    def test_metrics_download_unknown_format_is_400(self) -> None:
        response = self._client(MagicMock()).get(
            "/api/metrics/download", params={"format": "xlsx"}
        )
        assert response.status_code == 400
        assert "xlsx" in response.json()["detail"]

    @staticmethod
    def _write_sample(stack, *, ts: str) -> None:
        path = stack.root / METRICS_DIR / METRICS_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": ts,
            "host": {"cpus": 2, "loadavg": [1.0], "memory": {"used_percent": 10}},
            "containers": [
                {
                    "service": "raft-gate",
                    "role": "gate",
                    "group": "raft",
                    "cpu_percent": 4.0,
                    "memory": {"used_percent": 20},
                }
            ],
        }
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
