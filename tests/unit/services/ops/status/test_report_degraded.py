"""Status degraded-host report coverage."""

from __future__ import annotations

from io import StringIO

from raft.adapters.host import HostResources
from raft.services.ops.status.models import AllocatedResources
from raft.services.ops.status.report import StatusReportWriter
from raft.services.ops.status.service import Status

from ....base import RaftTestCase
from .fixtures import StatusFixtures


class TestStatusReportDegraded(RaftTestCase):
    def test_report_degraded_host(self) -> None:
        empty = Status._host_status(
            HostResources(cpus=None, loadavg=None, memory=None, disk=None, uptime_seconds=None)
        )
        assert empty.memory is None and empty.disk_path is None
        text = self._render(self._degraded_snapshot(empty))
        assert "load: -" in text and " / -" in text
        assert "1.0KiB / 2.0KiB" in text

    def _degraded_snapshot(self, host):
        return StatusFixtures.snapshot(
            StatusFixtures.container(
                "app",
                app="app",
                status="not running",
                uptime=None,
                cpu=None,
                mem_used=None,
                mem_limit=None,
                mem_pct=None,
                pids=None,
                allocated=AllocatedResources("0.5", "", "0.1", "32M"),
            ),
            StatusFixtures.container("app2", app="app2"),
            host=host,
        )

    def _render(self, snap) -> str:
        out = StringIO()
        assert StatusReportWriter().write(snap, out=out, color=False) == 0
        return out.getvalue()
