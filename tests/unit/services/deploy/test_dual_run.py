"""Dual-run cutover gate: skip tmp when idle / not running."""

from __future__ import annotations

from pathlib import Path

from raft.models.app import App
from raft.models.state.scaling_store import ScalingStore
from raft.services.deploy.dual_run import DualRunCutover


class TestDualRunCutover:
    def test_needed_when_live_replica(self, tmp_path: Path) -> None:
        app = App(name="demo-api", public_host="demo.test", source="local", path="apps/x")
        assert DualRunCutover(tmp_path).needed(app, ["demo-api", "raft-gate"]) is True

    def test_not_needed_when_not_running(self, tmp_path: Path) -> None:
        app = App(name="demo-api", public_host="demo.test", source="local", path="apps/x")
        assert DualRunCutover(tmp_path).needed(app, ["raft-gate", "raft-router"]) is False

    def test_not_needed_when_scaled_to_zero(self, tmp_path: Path) -> None:
        app = App(name="demo-api", public_host="demo.test", source="local", path="apps/x")
        ScalingStore(tmp_path).mark_scaled_to_zero("demo-api")
        assert DualRunCutover(tmp_path).needed(app, ["demo-api", "raft-gate"]) is False
