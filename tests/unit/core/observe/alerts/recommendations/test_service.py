"""Alert recommendations service: list, dismiss, apply without channels."""

from pathlib import Path

from raft.core.core.models.state.recommendation_dismissals import AlertDismissalStore
from raft.core.observe.alerts.recommendations import AlertRecommendations
from raft.core.observe.alerts.service import AlertRulesService
from tests.unit.base import RaftTestCase


class TestAlertRecommendations(RaftTestCase):
    def _prep(self) -> Path:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text(
            "notifications:\n  enabled: true\n  channels: []\n",
            encoding="utf-8",
        )
        return home

    def test_list_includes_oom(self) -> None:
        items = AlertRecommendations(self._prep()).list_public()["recommendations"]
        assert "any-service-oom" in {item["id"] for item in items}
        assert all(item["rule"]["channelIds"] == [] for item in items)

    def test_apply_without_channels(self) -> None:
        home = self._prep()
        result = AlertRecommendations(home).apply("any-service-oom")
        assert result["rule"]["id"] == "any-service-oom"
        assert result["rule"]["channelIds"] == []
        assert AlertRulesService(home).get("any-service-oom").channel_ids == ()
        assert "any-service-oom" not in {
            i["id"] for i in result["recommendations"]
        }

    def test_dismiss(self) -> None:
        home = self._prep()
        AlertRecommendations(home).dismiss("any-service-high-memory")
        left = {
            i["id"]
            for i in AlertRecommendations(home).list_public()["recommendations"]
        }
        assert "any-service-high-memory" not in left
        assert AlertDismissalStore(home).list_ids() == {"any-service-high-memory"}

    def test_apply_unknown(self) -> None:
        try:
            AlertRecommendations(self._prep()).apply("missing-rec")
            raise AssertionError("expected KeyError")
        except KeyError:
            pass

    def test_preview_ids(self) -> None:
        assert "any-service-oom" in AlertRecommendations(self._prep()).preview_ids()
