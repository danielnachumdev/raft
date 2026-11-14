"""ContainerStatusSource story: target * includes apps + control plane (#398)."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Sequence

from raft.core.core.config.paths.metrics_paths import MetricsPaths
from raft.core.core.models.state.manual_stop_store import ManualStopStore
from raft.core.core.models.state.redeploying_store import RedeployingStore
from raft.core.core.models.state.scaling_store import ScalingStore
from raft.core.observe.alerts.signals.context import SignalContext
from raft.core.observe.alerts.signals.control.container_status_source import (
    ContainerStatusSource,
)
from tests.unit.base import RaftTestCase

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def _write_resources(home: Path, containers: List[dict]) -> None:
    path = MetricsPaths(home).resources()
    path.parent.mkdir(parents=True, exist_ok=True)
    sample = {"ts": NOW.isoformat(), "containers": containers}
    path.write_text(json.dumps(sample) + "\n", encoding="utf-8")


def _ctx(
    home: Path,
    *,
    apps: Sequence[str],
    control_plane: Sequence[str] = (),
) -> SignalContext:
    return SignalContext(
        home, NOW, app_names=list(apps), control_plane_names=list(control_plane)
    )


def _star(ctx: SignalContext) -> List[Any]:
    return ContainerStatusSource().query(
        {"target": "*"}, window_seconds=300, ctx=ctx
    )


class TestContainerStatusWildcardStory(RaftTestCase):
    """Operator alerts on target *; scaled apps skip; control plane is included.

    Scenario:
      1) * sees demo-api running; scaledToZero demo-web returns no series.
      2) * also includes raft-router / raft-gate from control_plane_names.
    """

    def test_star_sees_app_and_skips_scaled_to_zero(self) -> None:
        home = Path(self.tmp_path)
        _write_resources(home, [{"service": "demo-api", "status": "running"}])
        ctx = _ctx(home, apps=["demo-api", "demo-web"])
        assert any(s.subject == "demo-api" for s in _star(ctx))
        ScalingStore(home).mark_scaled_to_zero("demo-web")
        assert (
            ContainerStatusSource().query(
                {"target": "demo-web"}, window_seconds=300, ctx=ctx
            )
            == []
        )

    def test_skips_manual_stop_target_and_wildcard(self) -> None:
        home = Path(self.tmp_path)
        _write_resources(
            home,
            [
                {"service": "demo-api", "status": "not running"},
                {"service": "demo-web", "status": "running"},
            ],
        )
        ManualStopStore(home).mark("demo-api")
        ctx = _ctx(home, apps=["demo-api", "demo-web"])
        assert (
            ContainerStatusSource().query(
                {"target": "demo-api"}, window_seconds=300, ctx=ctx
            )
            == []
        )
        subjects = {s.subject for s in _star(ctx)}
        assert "demo-api" not in subjects
        assert "demo-web" in subjects

    def test_skips_redeploying_target_and_wildcard(self) -> None:
        home = Path(self.tmp_path)
        _write_resources(
            home,
            [
                {"service": "demo-api", "status": "not running"},
                {"service": "demo-web", "status": "running"},
            ],
        )
        RedeployingStore(home).mark("demo-api")
        ctx = _ctx(home, apps=["demo-api", "demo-web"])
        assert (
            ContainerStatusSource().query(
                {"target": "demo-api"}, window_seconds=300, ctx=ctx
            )
            == []
        )
        subjects = {s.subject for s in _star(ctx)}
        assert "demo-api" not in subjects
        assert "demo-web" in subjects

    def test_star_includes_control_plane_subjects(self) -> None:
        home = Path(self.tmp_path)
        _write_resources(
            home,
            [
                {"service": "raft-router", "status": "crash-looping"},
                {"service": "demo-api", "status": "running"},
            ],
        )
        ctx = _ctx(
            home,
            apps=["demo-api"],
            control_plane=["raft-gate", "raft-router", "raft-controller"],
        )
        by_subject = {s.subject: s for s in _star(ctx)}
        assert by_subject["raft-router"].points[-1].value == "crash-looping"
        assert "raft-gate" in by_subject and "demo-api" in by_subject
