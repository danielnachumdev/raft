"""Status surfaces Docker health as distinct STATUS labels."""

from __future__ import annotations

from unittest.mock import MagicMock

from raft.ops.status.formatters import StatusFormatters
from raft.ops.status.models import STATUS_STARTING, STATUS_UNHEALTHY

from .base import StatusTestCase
from . import fixtures as status_fx


class TestStatusHealth(StatusTestCase):
    def test_formatter_maps_health(self) -> None:
        assert StatusFormatters.container_status("running", "none") == "running"
        assert StatusFormatters.container_status("running", "healthy") == "running"
        assert StatusFormatters.container_status("running", "unhealthy") == STATUS_UNHEALTHY
        assert StatusFormatters.container_status("running", "starting") == STATUS_STARTING
        assert StatusFormatters.container_status("restarting", "none") == "crash-looping"
        assert StatusFormatters.container_status("", "none") == "unknown"

    def test_collect_marks_unhealthy(self) -> None:
        status = self.make_status("app")
        self._wire_unhealthy_app(status_fx.mock_containers_idle(status))
        with self.patch_host():
            snap = status.collect()
        by_svc = {c.service: c for c in snap.containers}
        assert by_svc["raft-gate"].status == "running"
        assert by_svc["app"].status == STATUS_UNHEALTHY

    def test_collect_edge_without_healthcheck(self) -> None:
        """nginx edge has no Health key; must still show running + uptime."""
        status = self.make_status("app")
        self._wire_edge_no_health(status_fx.mock_containers_idle(status))
        with self.patch_host():
            snap = status.collect()
        by_svc = {c.service: c for c in snap.containers}
        for name in ("raft-gate", "raft-router", "raft-controller"):
            row = by_svc[name]
            assert row.status == "running", name
            assert row.uptime_seconds is not None and row.uptime_seconds > 0, name

    @staticmethod
    def _wire_unhealthy_app(gateway: MagicMock) -> None:
        gateway.collect.return_value = {
            "raft-gate": status_fx.runtime_row("gatecid", health="none"),
            "app": status_fx.runtime_row("appcid", health="unhealthy"),
        }

    @staticmethod
    def _wire_edge_no_health(gateway: MagicMock) -> None:
        gateway.collect.return_value = {
            name: status_fx.runtime_row(f"{name}-cid", memory_bytes=0)
            for name in ("raft-gate", "raft-router", "raft-controller")
        }
