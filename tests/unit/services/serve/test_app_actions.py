"""Serve API service action routes (up/down/redeploy)."""

from unittest.mock import MagicMock

from raft.core.core.errors.cta import OperatorError

from tests.unit.base import RaftTestCase, AppMakers, StackMakers
from tests.unit.services.serve import fixtures as serve_fx


class TestServeAppActions(RaftTestCase):
    def test_api_service_up_ok(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"),))
        actions = MagicMock()
        actions.up.return_value = {
            "ok": True,
            "action": "up",
            "service": "site",
            "no_deps": False,
            "started_deps": [],
        }
        client = serve_fx.client_with_actions(stack, actions)
        response = client.post("/api/service/site/up")
        assert response.status_code == 200
        assert response.json()["action"] == "up"
        actions.up.assert_called_once_with("site", no_deps=False)

    def test_api_service_up_no_deps(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"),))
        actions = MagicMock()
        actions.up.return_value = {
            "ok": True,
            "action": "up",
            "service": "site",
            "no_deps": True,
            "started_deps": [],
        }
        client = serve_fx.client_with_actions(stack, actions)
        response = client.post("/api/service/site/up?no_deps=true")
        assert response.status_code == 200
        actions.up.assert_called_once_with("site", no_deps=True)

    def test_api_service_down_ok(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"),))
        actions = MagicMock()
        actions.down.return_value = {"ok": True, "action": "down", "service": "site"}
        client = serve_fx.client_with_actions(stack, actions)
        response = client.post("/api/service/site/down")
        assert response.status_code == 200
        actions.down.assert_called_once_with("site")

    def test_api_service_redeploy_ok(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"),))
        actions = MagicMock()
        actions.redeploy.return_value = {
            "ok": True,
            "action": "redeploy",
            "service": "site",
        }
        client = serve_fx.client_with_actions(stack, actions)
        response = client.post("/api/service/site/redeploy")
        assert response.status_code == 200
        actions.redeploy.assert_called_once_with("site")

    def test_api_service_redeploy_dashboard_started_is_202(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path)
        actions = MagicMock()
        actions.redeploy.return_value = {
            "ok": True,
            "action": "redeploy",
            "service": "raft-dashboard",
            "started": True,
            "job_id": "job-abc",
        }
        client = serve_fx.client_with_actions(stack, actions)
        response = client.post("/api/service/raft-dashboard/redeploy")
        assert response.status_code == 202
        body = response.json()
        assert body["started"] is True
        assert body["job_id"] == "job-abc"

    def test_api_service_action_operator_error_is_400(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"),))
        actions = MagicMock()
        actions.redeploy.side_effect = OperatorError(
            "refusing to redeploy `controller`", has_fix=False
        )
        client = serve_fx.client_with_actions(stack, actions)
        response = client.post("/api/service/raft-controller/redeploy")
        assert response.status_code == 400
        assert "controller" in response.json()["detail"]

    def test_api_service_down_operator_error_is_400(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"),))
        actions = MagicMock()
        actions.down.side_effect = OperatorError(
            "cannot stop site", has_fix=False
        )
        client = serve_fx.client_with_actions(stack, actions)
        response = client.post("/api/service/site/down")
        assert response.status_code == 400
        assert "cannot stop" in response.json()["detail"]

    def test_api_service_action_unknown_is_404(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path)
        actions = MagicMock()
        actions.up.side_effect = OperatorError(
            "unknown logs target 'missing' (known: gate)",
        )
        client = serve_fx.client_with_actions(stack, actions)
        response = client.post("/api/service/missing/up")
        assert response.status_code == 404
