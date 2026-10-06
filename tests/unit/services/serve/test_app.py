"""App factory + route smoke tests for ``raft serve``."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from raft.controller.metrics import METRICS_DIR, METRICS_FILENAME
from raft.models.app import EDGE_GROUP
from raft.services.ops.status.models import StatusSnapshot
from raft.services.serve.app import ServeAppFactory
from raft.services.serve.service import DEFAULT_SERVE_PORT, Serve

from ...base import RaftTestCase, make_app, make_stack
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
    def client_with_actions(stack, actions):
        status = MagicMock()
        status.collect.return_value = _ServeFixtures.empty_snapshot()
        return TestClient(
            ServeAppFactory(stack, status=status, actions=actions).create()
        )

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
        assert data["control_plane"][0]["service"] == "raft-gate"
        assert data["apps"][0]["name"] == "site"
        assert data["apps"][0]["service"] == "site"

    def test_api_service_returns_detail(self) -> None:
        client, status = _ServeFixtures.client_and_status(
            make_stack(self.tmp_path), _ServeFixtures.full_snapshot()
        )
        response = client.get("/api/service/raft-gate")
        assert response.status_code == 200
        status.collect.assert_called_once()
        data = response.json()
        assert data["container"]["service"] == "raft-gate"
        assert data["presentation"]["name"] == "gate"
        assert data["presentation"]["role"] == "gate"

    def test_api_service_unknown_is_404(self) -> None:
        client, _ = _ServeFixtures.client_and_status(
            make_stack(self.tmp_path), _ServeFixtures.full_snapshot()
        )
        response = client.get("/api/service/missing")
        assert response.status_code == 404

    def test_api_service_start_ok(self) -> None:
        stack = make_stack(self.tmp_path, (make_app("site"),))
        actions = MagicMock()
        actions.start.return_value = {"ok": True, "action": "start", "service": "site"}
        client = _ServeFixtures.client_with_actions(stack, actions)
        response = client.post("/api/service/site/start")
        assert response.status_code == 200
        assert response.json()["action"] == "start"
        actions.start.assert_called_once_with("site")

    def test_api_service_stop_ok(self) -> None:
        stack = make_stack(self.tmp_path, (make_app("site"),))
        actions = MagicMock()
        actions.stop.return_value = {"ok": True, "action": "stop", "service": "site"}
        client = _ServeFixtures.client_with_actions(stack, actions)
        response = client.post("/api/service/site/stop")
        assert response.status_code == 200
        actions.stop.assert_called_once_with("site")

    def test_api_service_redeploy_ok(self) -> None:
        stack = make_stack(self.tmp_path, (make_app("site"),))
        actions = MagicMock()
        actions.redeploy.return_value = {
            "ok": True,
            "action": "redeploy",
            "service": "site",
        }
        client = _ServeFixtures.client_with_actions(stack, actions)
        response = client.post("/api/service/site/redeploy")
        assert response.status_code == 200
        actions.redeploy.assert_called_once_with("site")

    def test_api_service_action_operator_error_is_400(self) -> None:
        from raft.errors.cta import OperatorError

        stack = make_stack(self.tmp_path, (make_app("site"),))
        actions = MagicMock()
        actions.redeploy.side_effect = OperatorError(
            "refusing to redeploy `gate`", has_fix=False
        )
        client = _ServeFixtures.client_with_actions(stack, actions)
        response = client.post("/api/service/raft-gate/redeploy")
        assert response.status_code == 400
        assert "gate" in response.json()["detail"]

    def test_api_service_action_unknown_is_404(self) -> None:
        from raft.errors.cta import OperatorError

        stack = make_stack(self.tmp_path)
        actions = MagicMock()
        actions.start.side_effect = OperatorError(
            "unknown logs target 'missing' (known: gate)",
        )
        client = _ServeFixtures.client_with_actions(stack, actions)
        response = client.post("/api/service/missing/start")
        assert response.status_code == 404

    def test_spa_deep_link_serves_index(self) -> None:
        client, status = _ServeFixtures.client_and_status(
            make_stack(self.tmp_path), _ServeFixtures.empty_snapshot()
        )
        response = client.get("/service/raft-gate")
        assert response.status_code == 200
        status.collect.assert_not_called()
        assert 'id="root"' in response.text

    def test_unknown_api_path_is_not_spa(self) -> None:
        client, _ = _ServeFixtures.client_and_status(
            make_stack(self.tmp_path), _ServeFixtures.empty_snapshot()
        )
        response = client.get("/api/nope")
        assert response.status_code == 404
        assert "text/html" not in response.headers.get("content-type", "")

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
        assert data["bounds"]["max_window_seconds"] >= 86400
        assert data["clamped"] is False

    def test_api_metrics_rejects_bad_start(self) -> None:
        client, _ = _ServeFixtures.client_and_status(
            make_stack(self.tmp_path), _ServeFixtures.empty_snapshot()
        )
        res = client.get("/api/metrics", params={"start": "not-a-time"})
        assert res.status_code == 400

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
