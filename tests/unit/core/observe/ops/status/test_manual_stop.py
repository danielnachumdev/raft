"""Status collect/report treat operator Down as manual-stop."""

from __future__ import annotations

from io import StringIO

from raft.core.core.models.state.manual_stop_store import ManualStopStore
from raft.core.core.models.state.scaling_store import ScalingStore
from raft.core.observe.ops.status import Status
from raft.core.observe.ops.status.models import (
    STATUS_MANUAL_STOP,
    STATUS_NOT_RUNNING,
    STATUS_SCALED_TO_ZERO,
)
from raft.core.observe.ops.status.report import StatusReportWriter

from tests.unit.base import AppMakers
from tests.unit.core.observe.ops.status.base import StatusTestCase
from . import fixtures as status_fx


class TestStatusManualStop(StatusTestCase):
    def _status(self, *names: str) -> Status:
        apps = tuple(AppMakers.make_app(n) for n in names) or (
            AppMakers.make_app("app"),
        )
        status = self.make_status(apps=apps)
        status_fx.mock_docker_idle(status)
        return status

    def test_collect_marks_manual_stop(self) -> None:
        status = self._status("app")
        ManualStopStore(self.tmp_path).mark("app")
        with self.patch_host():
            snap = status.collect()
        app = next(c for c in snap.containers if c.app == "app")
        assert app.status == STATUS_MANUAL_STOP

    def test_manual_stop_wins_over_scaled_to_zero(self) -> None:
        status = self._status("app")
        ManualStopStore(self.tmp_path).mark("app")
        ScalingStore(self.tmp_path).mark_scaled_to_zero("app")
        with self.patch_host():
            snap = status.collect()
        app = next(c for c in snap.containers if c.app == "app")
        assert app.status == STATUS_MANUAL_STOP
        assert app.status != STATUS_SCALED_TO_ZERO

    def test_collect_keeps_not_running_without_marker(self) -> None:
        status = self._status("app")
        with self.patch_host():
            snap = status.collect()
        app = next(c for c in snap.containers if c.app == "app")
        assert app.status == STATUS_NOT_RUNNING

    def test_report_footnote_for_manual_stop(self) -> None:
        snap = status_fx.snapshot(
            status_fx.container(
                "app",
                app="app",
                status=STATUS_MANUAL_STOP,
                uptime=None,
                cpu=None,
                mem_used=None,
                mem_limit=None,
                mem_pct=None,
                pids=None,
            )
        )
        out = StringIO()
        assert StatusReportWriter().write(snap, out=out, color=False) == 0
        text = out.getvalue()
        assert STATUS_MANUAL_STOP in text
        assert "intentional" in text
