"""AlertsInboxSource feature-detect and mapping."""

from unittest.mock import MagicMock, patch

from raft.core.observe.inbox.sources.alerts import (
    HREF,
    SOURCE_ID,
    AlertsInboxSource,
)
from raft.core.observe.inbox.sources.registry import InboxSourceRegistry
from tests.unit.base import RaftTestCase


class TestAlertsInboxSource(RaftTestCase):
    def test_try_create_when_absent(self) -> None:
        with patch(
            "raft.core.observe.inbox.sources.alerts.AlertRecommendations",
            None,
        ):
            assert AlertsInboxSource.try_create(self.tmp_path) is None
            try:
                AlertsInboxSource(self.tmp_path)
                raise AssertionError("expected RuntimeError")
            except RuntimeError:
                pass

    def test_maps_with_injected_catalog(self) -> None:
        fake = MagicMock()
        fake.list_public.return_value = {
            "recommendations": [
                {
                    "id": "any-service-oom",
                    "title": "OOM",
                    "summary": "Crash-loop",
                },
                1,
            ]
        }
        source = AlertsInboxSource.try_create(
            self.tmp_path, recommendations=fake
        )
        assert source is not None
        items = source.list_items()
        assert items[0].id == f"{SOURCE_ID}:any-service-oom"
        assert items[0].href == HREF
        source.dismiss("any-service-oom")
        fake.dismiss.assert_called_once_with("any-service-oom")

    def test_try_create_when_package_present(self) -> None:
        fake_cls = MagicMock(return_value=MagicMock())
        with patch(
            "raft.core.observe.inbox.sources.alerts.AlertRecommendations",
            fake_cls,
        ):
            source = AlertsInboxSource.try_create(self.tmp_path)
            assert source is not None
            assert source.source_id == SOURCE_ID
            fake_cls.assert_called_once_with(self.tmp_path)

    def test_registry_wires_alerts_and_extra(self) -> None:
        extra = MagicMock()
        extra.source_id = "custom"
        alerts = MagicMock()
        with patch.object(AlertsInboxSource, "try_create", return_value=alerts):
            sources = InboxSourceRegistry.default(
                self.tmp_path, extra=[extra]
            )
        assert sources[0].source_id == "firewall-recommendation"
        assert sources[1] is alerts
        assert sources[2] is extra

    def test_registry_skips_alerts_when_unavailable(self) -> None:
        with patch.object(AlertsInboxSource, "try_create", return_value=None):
            sources = InboxSourceRegistry.default(self.tmp_path)
        assert len(sources) == 1
        assert sources[0].source_id == "firewall-recommendation"
