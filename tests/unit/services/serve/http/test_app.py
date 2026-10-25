"""App factory + status/SPA route smoke tests for ``raft serve``."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from raft.services.serve.http.app import ServeAppFactory

from tests.unit.base import RaftTestCase, StackMakers
from tests.unit.core.observe.ops.status import fixtures as status_fx
from tests.unit.services.serve import fixtures as serve_fx


class TestServeAppFactory(RaftTestCase):
    def test_index_serves_spa_shell_without_collect(self) -> None:
        client, status = serve_fx.client_and_status(
            StackMakers.make_stack(self.tmp_path), serve_fx.full_snapshot()
        )
        response = client.get("/")
        body = response.text
        assert response.status_code == 200
        status.collect.assert_not_called()
        assert 'id="root"' in body
        assert "/assets/" in body
        assert "raft dashboard" in body

    def test_api_status_returns_json_from_collect(self) -> None:
        client, status = serve_fx.client_and_status(
            StackMakers.make_stack(self.tmp_path), serve_fx.full_snapshot()
        )
        response = client.get("/api/status")
        assert response.status_code == 200
        status.collect.assert_called_once_with(
            refresh_apps=True, include_stats=False
        )
        data = response.json()
        assert "host" in data and "containers" in data
        assert "resources_as_of" in data
        names = [r["name"] for r in data["control_plane"]]
        assert names == ["gate", "router", "controller"]
        assert data["control_plane"][0]["service"] == "raft-gate"
        assert data["apps"][0]["name"] == "site"
        assert data["apps"][0]["service"] == "site"

    def test_api_status_includes_installed_version(self) -> None:
        client, _ = serve_fx.client_and_status(
            StackMakers.make_stack(self.tmp_path), serve_fx.full_snapshot()
        )
        with patch(
            "raft.core.observe.read.status.InstalledVersion.package_version",
            return_value="0.11.0",
        ), patch(
            "raft.core.observe.read.status.InstalledVersion.line",
            return_value="raft 0.11.0",
        ), patch(
            "raft.core.observe.read.status.InstalledVersion.chrome_label",
            return_value="0.11.0",
        ):
            data = client.get("/api/status").json()
        assert data["version"] == {
            "package": "0.11.0",
            "line": "raft 0.11.0",
            "label": "0.11.0",
        }

    def test_api_service_returns_detail(self) -> None:
        client, status = serve_fx.client_and_status(
            StackMakers.make_stack(self.tmp_path), serve_fx.full_snapshot()
        )
        response = client.get("/api/service/raft-gate")
        assert response.status_code == 200
        status.collect.assert_called_once_with(
            refresh_apps=True, include_stats=True
        )
        data = response.json()
        assert data["container"]["service"] == "raft-gate"
        assert data["presentation"]["name"] == "gate"
        assert data["presentation"]["role"] == "gate"

    def test_api_service_unknown_is_404(self) -> None:
        client, _ = serve_fx.client_and_status(
            StackMakers.make_stack(self.tmp_path), serve_fx.full_snapshot()
        )
        response = client.get("/api/service/missing")
        assert response.status_code == 404

    def test_spa_deep_link_serves_index(self) -> None:
        client, status = serve_fx.client_and_status(
            StackMakers.make_stack(self.tmp_path), serve_fx.empty_snapshot()
        )
        response = client.get("/service/raft-gate")
        assert response.status_code == 200
        status.collect.assert_not_called()
        assert 'id="root"' in response.text

    def test_unknown_api_path_is_not_spa(self) -> None:
        client, _ = serve_fx.client_and_status(
            StackMakers.make_stack(self.tmp_path), serve_fx.empty_snapshot()
        )
        response = client.get("/api/nope")
        assert response.status_code == 404
        assert "text/html" not in response.headers.get("content-type", "")

    def test_api_status_empty_snapshot(self) -> None:
        client, _ = serve_fx.client_and_status(
            StackMakers.make_stack(self.tmp_path), serve_fx.empty_snapshot()
        )
        data = client.get("/api/status").json()
        assert data["control_plane"] == [] and data["apps"] == []

    def test_api_status_reloads_registry_including_worker(self) -> None:
        client, actions, logs = serve_fx.live_registry_client(self.tmp_path)
        serve_fx.write_out_of_band_apps(self.tmp_path)
        with patch(
            "raft.core.observe.ops.status.service.HostGateway.resources",
            return_value=status_fx.host(),
        ):
            data = client.get("/api/status").json()
        names = {row["service"] for row in data["apps"]}
        assert names == {"site", "demo-api", "demo-worker"}
        assert {app.name for app in actions.stack.apps} == names
        assert {app.name for app in logs.stack.apps} == names

    def test_api_metrics_reads_jsonl(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path)
        ts = datetime.now(timezone.utc).isoformat()
        serve_fx.write_metrics_sample(stack, ts=ts)
        client, _ = serve_fx.client_and_status(
            stack, serve_fx.empty_snapshot()
        )
        data = client.get("/api/metrics", params={"window": 3600}).json()
        assert data["cursor"] == ts
        assert {s["id"] for s in data["series"]} == {"host", "raft-gate"}
        assert data["bounds"]["max_window_seconds"] >= 86400
        assert data["clamped"] is False

    def test_api_metrics_rejects_bad_start(self) -> None:
        client, _ = serve_fx.client_and_status(
            StackMakers.make_stack(self.tmp_path), serve_fx.empty_snapshot()
        )
        res = client.get("/api/metrics", params={"start": "not-a-time"})
        assert res.status_code == 400

    def test_spa_assets_are_served(self) -> None:
        client, _ = serve_fx.client_and_status(
            StackMakers.make_stack(self.tmp_path), serve_fx.empty_snapshot()
        )
        index = client.get("/").text
        marker = 'src="/assets/'
        assert marker in index
        start = index.index(marker) + len('src="')
        end = index.index('"', start)
        asset = client.get(index[start:end])
        assert asset.status_code == 200
        assert len(asset.content) > 0

    def test_factory_builds_default_status(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path)
        with patch("raft.core.observe.read.status.Status") as status_cls:
            status_cls.return_value = MagicMock()
            ServeAppFactory(stack).create()
        status_cls.assert_called_once_with(stack)
