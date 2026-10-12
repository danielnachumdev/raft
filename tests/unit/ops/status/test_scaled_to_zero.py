"""Status collect/report treat intentional scale-to-zero distinctly."""

from __future__ import annotations

from io import StringIO

from raft.models.state.scaling_store import ScalingStore
from raft.ops.status import Status
from raft.ops.status.models import STATUS_NOT_RUNNING, STATUS_SCALED_TO_ZERO
from raft.ops.status.report import StatusReportWriter

from tests.unit.base import AppMakers
from .base import StatusTestCase
from . import fixtures as status_fx


class TestStatusScaledToZero(StatusTestCase):
    def _status(self, *names: str) -> Status:
        apps = tuple(AppMakers.make_app(n) for n in names) or (AppMakers.make_app("app"),)
        status = self.make_status(apps=apps)
        status_fx.mock_docker_idle(status)
        return status

    def test_collect_marks_scaled_to_zero(self) -> None:
        status = self._status("app")
        ScalingStore(self.tmp_path).mark_scaled_to_zero("app")
        with self.patch_host():
            snap = status.collect()
        app = next(c for c in snap.containers if c.app == "app")
        assert app.status == STATUS_SCALED_TO_ZERO
        assert app.uptime_seconds is None

    def test_collect_keeps_not_running_when_unscaled(self) -> None:
        status = self._status("app")
        with self.patch_host():
            snap = status.collect()
        app = next(c for c in snap.containers if c.app == "app")
        assert app.status == STATUS_NOT_RUNNING

    def test_report_footnote_for_scaled_to_zero(self) -> None:
        snap = status_fx.snapshot(
            status_fx.container(
                "app",
                app="app",
                status=STATUS_SCALED_TO_ZERO,
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
        assert STATUS_SCALED_TO_ZERO in text
        assert "intentional" in text
