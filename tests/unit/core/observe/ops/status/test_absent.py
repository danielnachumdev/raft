"""AbsentStatus resolves intentional vs unexpected missing containers."""

from pathlib import Path

from raft.core.core.models.state.manual_stop_store import ManualStopStore
from raft.core.core.models.state.redeploying_store import RedeployingStore
from raft.core.core.models.state.scaling_store import ScalingStore
from raft.core.observe.ops.status.absent import AbsentStatus
from raft.core.observe.ops.status.models import (
    STATUS_MANUAL_STOP,
    STATUS_NOT_RUNNING,
    STATUS_REDEPLOYING,
    STATUS_SCALED_TO_ZERO,
)

from tests.unit.base import RaftTestCase


class TestAbsentStatus(RaftTestCase):
    def test_edge_without_app_is_not_running(self) -> None:
        assert AbsentStatus.for_app(Path(self.tmp_path), None) == STATUS_NOT_RUNNING

    def test_manual_stop_and_scaled_precedence(self) -> None:
        root = Path(self.tmp_path)
        assert AbsentStatus.for_app(root, "demo-api") == STATUS_NOT_RUNNING
        ScalingStore(root).mark_scaled_to_zero("demo-api")
        assert AbsentStatus.for_app(root, "demo-api") == STATUS_SCALED_TO_ZERO
        ManualStopStore(root).mark("demo-api")
        assert AbsentStatus.for_app(root, "demo-api") == STATUS_MANUAL_STOP

    def test_redeploying_wins_over_manual_and_scaled(self) -> None:
        root = Path(self.tmp_path)
        ScalingStore(root).mark_scaled_to_zero("demo-api")
        ManualStopStore(root).mark("demo-api")
        RedeployingStore(root).mark("demo-api")
        assert AbsentStatus.for_app(root, "demo-api") == STATUS_REDEPLOYING
