"""AlertsJob attach/tick."""

from pathlib import Path
from unittest.mock import MagicMock
from raft.core.core.config.settings.alerts_config import AlertsConfig
from raft.services.controller.engine import JobOrchestrator
from raft.services.controller.engine.job import JobIds
from raft.services.controller.jobs.alerts import AlertsJob
from tests.unit.base import RaftTestCase


class TestAlertsJob(RaftTestCase):
    def test_attach_when_enabled(self) -> None:
        orch = JobOrchestrator()
        engine = MagicMock()
        AlertsJob(Path(self.tmp_path), AlertsConfig(), engine=engine).attach(orch)
        assert JobIds.ALERTS in orch.registered_ids()

    def test_skip_when_disabled(self) -> None:
        orch = JobOrchestrator()
        AlertsJob(
            Path(self.tmp_path), AlertsConfig(enabled=False), engine=MagicMock()
        ).attach(orch)
        assert JobIds.ALERTS not in orch.registered_ids()

    def test_tick_swallows(self) -> None:
        engine = MagicMock()
        engine.tick.side_effect = RuntimeError("boom")
        AlertsJob(Path(self.tmp_path), AlertsConfig(), engine=engine).tick()
