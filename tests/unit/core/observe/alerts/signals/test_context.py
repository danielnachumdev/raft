"""SignalContext."""
from datetime import datetime, timezone
from pathlib import Path
from raft.core.observe.alerts.signals.context import SignalContext
from tests.unit.base import RaftTestCase

class TestSignalContext(RaftTestCase):
    def test_apps_copy(self) -> None:
        ctx = SignalContext(Path("/tmp"), datetime(2026,1,1,tzinfo=timezone.utc), app_names=["demo-api"])
        assert ctx.app_names == ("demo-api",)
