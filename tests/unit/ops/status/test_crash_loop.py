"""Status surfaces crash-looping from Engine restart churn."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Optional
from unittest.mock import patch

from raft.ops.status import Status
from raft.ops.status.formatters import StatusFormatters
from raft.ops.status.models import STATUS_CRASH_LOOPING, STATUS_UNHEALTHY
from raft.ops.status.report import StatusReportWriter

from tests.unit.base import RaftTestCase, make_app, make_stack, write_applied_app
from .fixtures import StatusFixtures

_HOST_PATCH = "raft.ops.status.service.HostGateway.resources"


class TestStatusCrashLoop(RaftTestCase):
    def test_formatter_maps_crash_loop(self) -> None:
        assert self._status("running", restarts=5, uptime=60.0) == STATUS_CRASH_LOOPING
        assert self._status("restarting") == STATUS_CRASH_LOOPING
        assert self._status("running", health="unhealthy") == STATUS_UNHEALTHY

    @staticmethod
    def _status(
        status: str,
        *,
        health: str = "none",
        restarts: int = 0,
        uptime: Optional[float] = None,
    ) -> str:
        return StatusFormatters.container_status(
            status,
            health,
            restart_count=restarts,
            uptime_seconds=uptime,
        )

    def test_collect_marks_controller_crash_looping(self) -> None:
        write_applied_app(self.tmp_path, "app")
        status = Status(make_stack(self.tmp_path, (make_app("app"),)))
        gateway = StatusFixtures.mock_containers_idle(status)
        self._wire_controller_churn(gateway)
        with patch(_HOST_PATCH, return_value=StatusFixtures.host()):
            snap = status.collect()
        by_svc = {c.service: c for c in snap.containers}
        assert by_svc["raft-controller"].status == STATUS_CRASH_LOOPING
        assert by_svc["raft-gate"].status == "running"

    def test_collect_ignores_recovered_restarts(self) -> None:
        write_applied_app(self.tmp_path, "app")
        status = Status(make_stack(self.tmp_path, (make_app("app"),)))
        gateway = StatusFixtures.mock_containers_idle(status)
        gateway.collect.return_value = {
            "raft-controller": StatusFixtures.runtime_row(
                "ctrl",
                restart_count=40,
                started=(datetime.now(timezone.utc) - timedelta(hours=2))
                .isoformat()
                .replace("+00:00", "Z"),
            ),
        }
        with patch(_HOST_PATCH, return_value=StatusFixtures.host()):
            snap = status.collect()
        ctrl = next(c for c in snap.containers if c.service == "raft-controller")
        assert ctrl.status == "running"

    def test_report_footnote_for_crash_looping(self) -> None:
        snap = StatusFixtures.snapshot(
            StatusFixtures.container(
                "raft-controller",
                role="controller",
                group="raft",
                status=STATUS_CRASH_LOOPING,
            )
        )
        out = StringIO()
        assert StatusReportWriter().write(snap, out=out, color=False) == 0
        text = out.getvalue()
        assert STATUS_CRASH_LOOPING in text
        assert "RestartCount" in text

    @staticmethod
    def _wire_controller_churn(gateway) -> None:
        recent = (
            (datetime.now(timezone.utc) - timedelta(seconds=90))
            .isoformat()
            .replace("+00:00", "Z")
        )
        gateway.collect.return_value = {
            "raft-gate": StatusFixtures.runtime_row("gatecid"),
            "raft-controller": StatusFixtures.runtime_row(
                "ctrlcid",
                restart_count=629,
                started=recent,
            ),
        }
