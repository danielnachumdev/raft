"""Final serve API handler branches."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.notify.channel_delivery import ChannelDelivery
from raft.core.observe.notify.delivery_result import DeliveryResult
from raft.services.serve.alerts import ServeAlertsApi
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestServeAlertsApiFinal(RaftTestCase):
    def _setup(self):
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text(
            "notifications: {enabled: true, channels: []}\n", encoding="utf-8"
        )
        api = ServeAlertsApi(Stack(root=home, apps=()))
        app = FastAPI()
        api.register(app)
        return TestClient(app), api

    def test_enabled_operator_error(self) -> None:
        client, api = self._setup()
        client.post("/api/alerts/rules", json=RULE)
        with patch.object(
            api._service, "set_enabled", side_effect=OperatorError("bad\nFix: x")
        ):
            assert (
                client.post(
                    "/api/alerts/rules/demo-api-5xx-rate/enabled",
                    json={"enabled": True},
                ).status_code
                == 400
            )

    def test_delete_missing_and_test_paths(self) -> None:
        client, api = self._setup()
        assert client.delete("/api/alerts/rules/missing").status_code == 404
        with patch(
            "raft.services.serve.alerts.api.AlertTester"
        ) as Tester:
            Tester.return_value.send.side_effect = KeyError("x")
            assert (
                client.post("/api/alerts/rules/demo-api-5xx-rate/test").status_code
                == 404
            )
        ok = ChannelDelivery("c1", "webhook", DeliveryResult.success())
        assert "1 of 1" in ServeAlertsApi._test_message([ok])
        assert "No deliverable" in ServeAlertsApi._test_message([])

    def test_delete_and_dry_run_operator_error(self) -> None:
        client, api = self._setup()
        client.post("/api/alerts/rules", json=RULE)
        with patch.object(
            api._service, "delete", side_effect=OperatorError("bad\nFix: x")
        ):
            assert (
                client.delete("/api/alerts/rules/demo-api-5xx-rate").status_code == 400
            )
        with patch.object(
            api._service._parser, "parse", side_effect=OperatorError("bad\nFix: x")
        ):
            assert (
                client.post("/api/alerts/dry-run", json={"rule": RULE}).status_code
                == 400
            )
