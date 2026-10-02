"""Status collect/report treat intentional scale-to-zero distinctly."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from raft.models.scaling_store import ScalingStore
from raft.services.ops.status import Status
from raft.services.ops.status.models import STATUS_NOT_RUNNING, STATUS_SCALED_TO_ZERO
from raft.services.ops.status.report import StatusReportWriter

from ....base import RaftTestCase, make_app, make_stack, write_applied_app
from .fixtures import StatusFixtures

_HOST_PATCH = "raft.services.ops.status.service.HostGateway.resources"


class TestStatusScaledToZero(RaftTestCase):
    def _status(self, *names: str) -> Status:
        apps = tuple(make_app(n) for n in names) or (make_app("app"),)
        for app in apps:
            write_applied_app(self.tmp_path, app.name)
        status = Status(make_stack(self.tmp_path, apps))
        StatusFixtures.mock_docker_idle(status)
        return status

    def test_collect_marks_scaled_to_zero(self) -> None:
        status = self._status("app")
        ScalingStore(self.tmp_path).mark_scaled_to_zero("app")
        with patch(_HOST_PATCH, return_value=StatusFixtures.host()):
            snap = status.collect()
        app = next(c for c in snap.containers if c.app == "app")
        assert app.status == STATUS_SCALED_TO_ZERO
        assert app.uptime_seconds is None

    def test_collect_keeps_not_running_when_unscaled(self) -> None:
        status = self._status("app")
        with patch(_HOST_PATCH, return_value=StatusFixtures.host()):
            snap = status.collect()
        app = next(c for c in snap.containers if c.app == "app")
        assert app.status == STATUS_NOT_RUNNING

    def test_report_footnote_for_scaled_to_zero(self) -> None:
        snap = StatusFixtures.snapshot(
            StatusFixtures.container(
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
