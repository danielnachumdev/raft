"""App factory + route smoke tests for ``raft serve``."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from raft.controller.metrics import METRICS_DIR, METRICS_FILENAME
from raft.models import EDGE_GROUP
from raft.services.ops.status.models import StatusSnapshot
from raft.services.serve.app import ServeAppFactory
from raft.services.serve.service import DEFAULT_SERVE_PORT, Serve

from ...base import RaftTestCase, make_stack
from ...services.ops.status.fixtures import StatusFixtures


class _ServeFixtures:
    @staticmethod
    def full_snapshot() -> StatusSnapshot:
        fx = StatusFixtures
        return StatusSnapshot(
            host=fx.empty_host_status(),
            containers=(
                fx.container("raft-gate", role="gate", group=EDGE_GROUP),
                fx.container("raft-router", role="router", group=EDGE_GROUP),
                fx.container("raft-controller", role="controller", group=EDGE_GROUP),
                fx.container("site", role="app", app="site", status="not running", uptime=None),
            ),
        )

    @staticmethod
    def empty_snapshot() -> StatusSnapshot:
        return StatusSnapshot(host=StatusFixtures.empty_host_status(), containers=())

    @staticmethod
    def client_and_status(stack, snapshot: StatusSnapshot):
        status = MagicMock()
        status.collect.return_value = snapshot
        return TestClient(ServeAppFactory(stack, status=status).create()), status

    @staticmethod
    def write_metrics_sample(stack, *, ts: str) -> None:
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


class TestServeAppFactory(RaftTestCase):
    def test_index_serves_spa_shell_without_collect(self) -> None:
        client, status = _ServeFixtures.client_and_status(
            make_stack(self.tmp_path), _ServeFixtures.full_snapshot()
        )
        response = client.get("/")
        body = response.text
        assert response.status_code == 200
        status.collect.assert_not_called()
        assert 'id="root"' in body
        assert "/assets/" in body
        assert "raft serve" in body

    def test_api_status_returns_json_from_collect(self) -> None:
        client, status = _ServeFixtures.client_and_status(
            make_stack(self.tmp_path), _ServeFixtures.full_snapshot()
        )
        response = client.get("/api/status")
        assert response.status_code == 200
        status.collect.assert_called_once()
        data = response.json()
        assert "host" in data and "containers" in data
        names = [r["name"] for r in data["control_plane"]]
        assert names == ["gate", "router", "controller"]
        assert data["apps"][0]["name"] == "site"

    def test_api_status_empty_snapshot(self) -> None:
        client, _ = _ServeFixtures.client_and_status(
            make_stack(self.tmp_path), _ServeFixtures.empty_snapshot()
        )
        data = client.get("/api/status").json()
        assert data["control_plane"] == [] and data["apps"] == []

    def test_api_metrics_reads_jsonl(self) -> None:
        stack = make_stack(self.tmp_path)
        ts = datetime.now(timezone.utc).isoformat()
        _ServeFixtures.write_metrics_sample(stack, ts=ts)
        client, _ = _ServeFixtures.client_and_status(stack, _ServeFixtures.empty_snapshot())
        data = client.get("/api/metrics", params={"window": 3600}).json()
        assert data["cursor"] == ts
        assert {s["id"] for s in data["series"]} == {"host", "raft-gate"}

    def test_spa_assets_are_served(self) -> None:
        client, _ = _ServeFixtures.client_and_status(
            make_stack(self.tmp_path), _ServeFixtures.empty_snapshot()
        )
        index = client.get("/").text
        # Hashed asset path from Vite build, e.g. /assets/index-xxxxx.js
        marker = 'src="/assets/'
        assert marker in index
        start = index.index(marker) + len('src="')
        end = index.index('"', start)
        asset_path = index[start:end]
        asset = client.get(asset_path)
        assert asset.status_code == 200
        assert len(asset.content) > 0

    def test_factory_builds_default_status(self) -> None:
        stack = make_stack(self.tmp_path)
        with patch("raft.services.read.status.Status") as status_cls:
            status_cls.return_value = MagicMock()
            ServeAppFactory(stack).create()
        status_cls.assert_called_once_with(stack)


class TestServeRun(RaftTestCase):
    def test_run_prints_instructions_and_starts_uvicorn(self, capsys) -> None:
        with patch("raft.services.serve.service.uvicorn.run") as run:
            Serve(make_stack(self.tmp_path)).run(port=DEFAULT_SERVE_PORT)
        out = capsys.readouterr().out
        assert "http://127.0.0.1:8787/" in out
        assert "ssh -L 8787:127.0.0.1:8787" in out
        run.assert_called_once()
        args, kwargs = run.call_args
        assert kwargs["host"] == "127.0.0.1" and kwargs["port"] == 8787
        assert args[0] is not None
