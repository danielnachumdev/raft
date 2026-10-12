"""Status surfaces crash-looping from Engine restart churn."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Optional
from unittest.mock import patch

from raft.core.observe.ops.status import Status
from raft.core.observe.ops.status.formatters import StatusFormatters
from raft.core.observe.ops.status.models import STATUS_CRASH_LOOPING, STATUS_UNHEALTHY
from raft.core.observe.ops.status.report import StatusReportWriter

from tests.unit.core.observe.ops.status.base import StatusTestCase
from . import fixtures as status_fx


class TestStatusCrashLoop(StatusTestCase):
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
        status = self.make_status("app")
        gateway = status_fx.mock_containers_idle(status)
        self._wire_controller_churn(gateway)
        with self.patch_host():
            snap = status.collect()
        by_svc = {c.service: c for c in snap.containers}
        assert by_svc["raft-controller"].status == STATUS_CRASH_LOOPING
        assert by_svc["raft-gate"].status == "running"

    def test_collect_ignores_recovered_restarts(self) -> None:
        status = self.make_status("app")
        gateway = status_fx.mock_containers_idle(status)
        gateway.collect.return_value = {
            "raft-controller": status_fx.runtime_row(
                "ctrl",
                restart_count=40,
                started=(datetime.now(timezone.utc) - timedelta(hours=2))
                .isoformat()
                .replace("+00:00", "Z"),
            ),
        }
        with self.patch_host():
            snap = status.collect()
        ctrl = next(c for c in snap.containers if c.service == "raft-controller")
        assert ctrl.status == "running"

    def test_report_footnote_for_crash_looping(self) -> None:
        snap = status_fx.snapshot(
            status_fx.container(
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
            "raft-gate": status_fx.runtime_row("gatecid"),
            "raft-controller": status_fx.runtime_row(
                "ctrlcid",
                restart_count=629,
                started=recent,
            ),
        }
