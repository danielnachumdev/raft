"""Stats degraded-host report coverage."""

from __future__ import annotations

from io import StringIO

from raft.adapters.host import HostResources
from raft.services.ops.stats.models import AllocatedResources
from raft.services.ops.stats.report import write_report
from raft.services.ops.stats.service import _host_stats

from ....base import RaftTestCase
from .fixtures import StatsFixtures


class TestStatsReportDegraded(RaftTestCase):
    def test_report_degraded_host(self) -> None:
        empty = _host_stats(
            HostResources(
                cpus=None, loadavg=None, memory=None, disk=None, uptime_seconds=None
            )
        )
        assert empty.memory is None and empty.disk_path is None
        snap = StatsFixtures.snapshot(
            StatsFixtures.container(
                "app", app="app", status="not running", uptime=None, cpu=None,
                mem_used=None, mem_limit=None, mem_pct=None, pids=None,
                allocated=AllocatedResources("0.5", "", "0.1", "32M"),
            ),
            StatsFixtures.container("app2", app="app2"),
            host=empty,
        )
        text = self._render(snap)
        assert "load: -" in text and " / -" in text
        assert "1.0KiB / 2.0KiB" in text

    def _render(self, snap) -> str:
        out = StringIO()
        assert write_report(snap, out=out, color=False) == 0
        return out.getvalue()
