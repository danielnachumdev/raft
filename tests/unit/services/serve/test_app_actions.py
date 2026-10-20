"""Serve API service action routes (start/stop/redeploy)."""

from unittest.mock import MagicMock

from raft.core.core.errors.cta import OperatorError

from tests.unit.base import RaftTestCase, AppMakers, StackMakers
from tests.unit.services.serve import fixtures as serve_fx


class TestServeAppActions(RaftTestCase):
    def test_api_service_start_ok(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"),))
        actions = MagicMock()
        actions.start.return_value = {
            "ok": True,
            "action": "start",
            "service": "site",
            "no_deps": False,
            "started_deps": [],
        }
        client = serve_fx.client_with_actions(stack, actions)
        response = client.post("/api/service/site/start")
        assert response.status_code == 200
        assert response.json()["action"] == "start"
        actions.start.assert_called_once_with("site", no_deps=False)

    def test_api_service_start_no_deps(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"),))
        actions = MagicMock()
        actions.start.return_value = {
            "ok": True,
            "action": "start",
            "service": "site",
            "no_deps": True,
            "started_deps": [],
        }
        client = serve_fx.client_with_actions(stack, actions)
        response = client.post("/api/service/site/start?no_deps=true")
        assert response.status_code == 200
        actions.start.assert_called_once_with("site", no_deps=True)

    def test_api_service_stop_ok(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"),))
        actions = MagicMock()
        actions.stop.return_value = {"ok": True, "action": "stop", "service": "site"}
        client = serve_fx.client_with_actions(stack, actions)
        response = client.post("/api/service/site/stop")
        assert response.status_code == 200
        actions.stop.assert_called_once_with("site")

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

    def test_api_service_action_operator_error_is_400(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"),))
        actions = MagicMock()
        actions.redeploy.side_effect = OperatorError(
            "refusing to redeploy `gate`", has_fix=False
        )
        client = serve_fx.client_with_actions(stack, actions)
        response = client.post("/api/service/raft-gate/redeploy")
        assert response.status_code == 400
        assert "gate" in response.json()["detail"]

    def test_api_service_action_unknown_is_404(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path)
        actions = MagicMock()
        actions.start.side_effect = OperatorError(
            "unknown logs target 'missing' (known: gate)",
        )
        client = serve_fx.client_with_actions(stack, actions)
        response = client.post("/api/service/missing/start")
        assert response.status_code == 404
