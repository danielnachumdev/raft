"""Serve API for alert recommendations."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from raft.core.core.models.stack import Stack
from raft.services.serve.alerts import ServeAlertsApi
from tests.unit.base import RaftTestCase


class TestServeAlertRecommendationsApi(RaftTestCase):
    def _client(self) -> TestClient:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text(
            "notifications:\n  enabled: true\n  channels: []\n",
            encoding="utf-8",
        )
        app = FastAPI()
        ServeAlertsApi(Stack(root=home, apps=())).register(app)
        return TestClient(app)

    def test_list_includes_oom(self) -> None:
        listed = self._client().get("/api/alerts/recommendations").json()
        oom = next(
            i for i in listed["recommendations"] if i["id"] == "any-service-oom"
        )
        assert oom["rule"]["channelIds"] == []

    def test_apply_creates_rule_without_channels(self) -> None:
        client = self._client()
        applied = client.post(
            "/api/alerts/recommendations/any-service-oom/apply"
        ).json()
        assert applied["rule"]["channelIds"] == []
        assert client.get("/api/alerts/rules/any-service-oom").status_code == 200
        assert "any-service-oom" not in {
            i["id"] for i in applied["recommendations"]
        }

    def test_dismiss(self) -> None:
        dismissed = self._client().post(
            "/api/alerts/recommendations/any-service-high-memory/dismiss"
        ).json()
        assert "any-service-high-memory" not in {
            i["id"] for i in dismissed["recommendations"]
        }

    def test_apply_unknown(self) -> None:
        assert (
            self._client().post("/api/alerts/recommendations/nope/apply").status_code
            == 404
        )
