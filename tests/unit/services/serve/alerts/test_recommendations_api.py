"""Serve API for alert recommendations."""

from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.alerts.service.rules_service import RuleConflict
from raft.services.serve.alerts import ServeAlertsApi
from tests.unit.base import RaftTestCase


class TestServeAlertRecommendationsApi(RaftTestCase):
    def _client(self):
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text(
            "notifications:\n  enabled: true\n  channels: []\n",
            encoding="utf-8",
        )
        api = ServeAlertsApi(Stack(root=home, apps=()))
        app = FastAPI()
        api.register(app)
        return TestClient(app), api

    def test_list_includes_oom(self) -> None:
        client, _api = self._client()
        listed = client.get("/api/alerts/recommendations").json()
        oom = next(
            i for i in listed["recommendations"] if i["id"] == "any-service-oom"
        )
        assert oom["rule"]["channelIds"] == []

    def test_apply_creates_rule_without_channels(self) -> None:
        client, _api = self._client()
        applied = client.post(
            "/api/alerts/recommendations/any-service-oom/apply"
        ).json()
        assert applied["rule"]["channelIds"] == []
        assert client.get("/api/alerts/rules/any-service-oom").status_code == 200
        assert "any-service-oom" not in {
            i["id"] for i in applied["recommendations"]
        }

    def test_dismiss(self) -> None:
        client, _api = self._client()
        dismissed = client.post(
            "/api/alerts/recommendations/any-service-high-memory/dismiss"
        ).json()
        assert "any-service-high-memory" not in {
            i["id"] for i in dismissed["recommendations"]
        }

    def test_apply_unknown(self) -> None:
        client, _api = self._client()
        assert client.post("/api/alerts/recommendations/nope/apply").status_code == 404

    def test_apply_conflict(self) -> None:
        client, api = self._client()
        with patch.object(
            api._recommendations, "apply", side_effect=RuleConflict("dup")
        ):
            assert (
                client.post(
                    "/api/alerts/recommendations/any-service-oom/apply"
                ).status_code
                == 409
            )

    def test_apply_operator_error(self) -> None:
        client, api = self._client()
        with patch.object(
            api._recommendations,
            "apply",
            side_effect=OperatorError("bad\nFix: check rule"),
        ):
            assert (
                client.post(
                    "/api/alerts/recommendations/any-service-oom/apply"
                ).status_code
                == 400
            )
