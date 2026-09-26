"""Status surfaces Docker health as distinct STATUS labels."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from raft.services.ops.status import Status
from raft.services.ops.status.formatters import StatusFormatters
from raft.services.ops.status.models import STATUS_STARTING, STATUS_UNHEALTHY

from ....base import RaftTestCase, make_app, make_stack, write_applied_app
from .fixtures import StatusFixtures

_HOST_PATCH = "raft.services.ops.status.service.HostProbe.collect"


class TestStatusHealth(RaftTestCase):
    def test_formatter_maps_health(self) -> None:
        assert StatusFormatters.container_status("running", "none") == "running"
        assert StatusFormatters.container_status("running", "healthy") == "running"
        assert StatusFormatters.container_status("running", "unhealthy") == STATUS_UNHEALTHY
        assert StatusFormatters.container_status("running", "starting") == STATUS_STARTING
        assert StatusFormatters.container_status("restarting", "none") == "restarting"
        assert StatusFormatters.container_status("", "none") == "unknown"

    def test_collect_marks_unhealthy(self) -> None:
        write_applied_app(self.tmp_path, "app")
        status = Status(make_stack(self.tmp_path, (make_app("app"),)))
        self._wire_unhealthy_app(StatusFixtures.mock_docker_idle(status))
        with patch(_HOST_PATCH, return_value=StatusFixtures.host()):
            snap = status.collect()
        by_svc = {c.service: c for c in snap.containers}
        assert by_svc["raft-gate"].status == "running"
        assert by_svc["app"].status == STATUS_UNHEALTHY

    def test_collect_edge_without_healthcheck(self) -> None:
        """nginx edge has no Health key; must still show running + uptime."""
        write_applied_app(self.tmp_path, "app")
        status = Status(make_stack(self.tmp_path, (make_app("app"),)))
        self._wire_edge_no_health(StatusFixtures.mock_docker_idle(status))
        with patch(_HOST_PATCH, return_value=StatusFixtures.host()):
            snap = status.collect()
        by_svc = {c.service: c for c in snap.containers}
        for name in ("raft-gate", "raft-router", "raft-controller"):
            row = by_svc[name]
            assert row.status == "running", name
            assert row.uptime_seconds is not None and row.uptime_seconds > 0, name

    @staticmethod
    def _wire_unhealthy_app(docker: MagicMock) -> None:
        docker.try_service_container_id.side_effect = lambda s: {
            "raft-gate": "gatecid",
            "app": "appcid",
        }.get(s)
        docker.containers_stats.return_value = {}
        started = StatusFixtures.started_iso()
        runtime = {
            "started_at": started,
            "nano_cpus": None,
            "memory_bytes": None,
        }
        docker.container_inspect_runtime.side_effect = [
            {**runtime, "status": "running", "health": "none"},
            {**runtime, "status": "running", "health": "unhealthy"},
        ]

    @staticmethod
    def _wire_edge_no_health(docker: MagicMock) -> None:
        ids = {
            "raft-gate": "gatecid",
            "raft-router": "routercid",
            "raft-controller": "ctrlcid",
        }
        docker.try_service_container_id.side_effect = lambda s: ids.get(s)
        docker.containers_stats.return_value = {}
        started = StatusFixtures.started_iso()
        none_health = {
            "status": "running",
            "health": "none",
            "started_at": started,
            "nano_cpus": 0,
            "memory_bytes": 0,
        }
        docker.container_inspect_runtime.side_effect = lambda _cid: dict(none_health)
