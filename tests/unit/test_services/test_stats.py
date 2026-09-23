"""Stats service — host + container snapshots."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from raft.adapters.host import HostDisk, HostMemory, HostResources
from raft.errors import OperatorError
from raft.services.stats import Stats
from raft.services.stats.models import EDGE_CPUS_LIMIT, AllocatedResources
from raft.services.stats.report import (
    _fmt_bytes,
    _fmt_percent,
    _fmt_uptime,
    write_report,
)
from raft.services.stats.service import _app_allocated, _parse_started_at

from ..base import RaftTestCase, make_app, make_stack, write_applied_app


def _fake_host() -> HostResources:
    return HostResources(
        cpus=4,
        loadavg=(0.1, 0.2, 0.3),
        memory=HostMemory(
            total_bytes=8 * 1024**3,
            available_bytes=4 * 1024**3,
            used_bytes=4 * 1024**3,
            used_percent=50.0,
        ),
        disk=HostDisk(
            path="/data",
            total_bytes=100 * 1024**3,
            used_bytes=40 * 1024**3,
            free_bytes=60 * 1024**3,
            used_percent=40.0,
        ),
        uptime_seconds=90061.0,
    )


class TestStatsHelpers:
    def test_parse_started_at(self) -> None:
        started = datetime.now(timezone.utc) - timedelta(hours=2, minutes=5)
        secs = _parse_started_at(started.isoformat().replace("+00:00", "Z"))
        assert secs is not None
        assert 7400 <= secs <= 7600
        assert _parse_started_at("") is None
        assert _parse_started_at("0001-01-01T00:00:00Z") is None
        assert _parse_started_at("not-a-date") is None
        naive = (datetime.now(timezone.utc) - timedelta(seconds=30)).replace(tzinfo=None)
        assert _parse_started_at(naive.isoformat()) is not None

    def test_formatters(self) -> None:
        assert _fmt_bytes(None) == "-"
        assert _fmt_bytes(-1) == "-"
        assert _fmt_bytes(512) == "512B"
        assert _fmt_bytes(1536) == "1.5KiB"
        assert _fmt_bytes(1024**4) == "1.0TiB"
        assert _fmt_percent(None) == "-"
        assert _fmt_percent(12.34) == "12.3%"
        assert _fmt_uptime(None) == "-"
        assert _fmt_uptime(45) == "45s"
        assert _fmt_uptime(3661) == "1h 1m"
        assert _fmt_uptime(90061) == "1d 1h 1m"


class TestStatsService(RaftTestCase):
    def test_collect_running_and_stopped(self) -> None:
        write_applied_app(self.tmp_path, "app")
        stack = make_stack(self.tmp_path, (make_app("app"),))
        stats = Stats(stack)
        docker = MagicMock()
        stats.docker = docker

        def try_id(service: str):
            return {"raft-gate": "gatecid", "raft-router": "routercid"}.get(service)

        docker.try_service_container_id.side_effect = try_id
        docker.containers_stats.return_value = {
            "gatecid": {
                "CPUPerc": "0.5%",
                "MemUsage": "3.0MiB / 64MiB",
                "MemPerc": "4.7%",
                "NetIO": "1kB / 2kB",
                "BlockIO": "0B / 0B",
                "PIDs": "5",
            },
            "routercid": {
                "CPUPerc": "0.1%",
                "MemUsage": "2.0MiB / 64MiB",
                "MemPerc": "3.1%",
                "NetIO": "0B / 0B",
                "BlockIO": "1B / 2B",
                "PIDs": "2",
            },
        }
        started = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        docker.container_inspect_runtime.side_effect = [
            {
                "status": "running",
                "started_at": started,
                "nano_cpus": 250000000,
                "memory_bytes": 67108864,
            },
            {
                "status": "running",
                "started_at": started,
                "nano_cpus": 250000000,
                "memory_bytes": 0,
            },
        ]

        with patch(
            "raft.services.stats.service.collect_host_resources",
            return_value=_fake_host(),
        ):
            snap = stats.collect()

        assert snap.host.cpus == 4
        assert snap.host.memory_total_bytes == 8 * 1024**3
        assert len(snap.containers) == 3
        gate, router, app = snap.containers
        assert gate.service == "raft-gate"
        assert gate.role == "gate"
        assert gate.status == "running"
        assert gate.cpu_percent == 0.5
        assert gate.allocated.cpus_limit == EDGE_CPUS_LIMIT
        assert gate.uptime_seconds is not None and gate.uptime_seconds >= 86000
        assert router.service == "raft-router"
        assert app.service == "app"
        assert app.status == "not running"
        assert app.app == "app"
        assert app.cpu_percent is None
        assert app.allocated.cpus_limit == "0.50"

    def test_app_allocated_fallback(self) -> None:
        stack = make_stack(self.tmp_path, (make_app("missing"),))
        allocated = _app_allocated(stack, stack.apps[0])
        assert allocated.memory_limit == "128M"
        bad = MagicMock()
        bad.spec_for.side_effect = OperatorError("boom")
        assert _app_allocated(bad, make_app("x")).cpus_limit == "0.50"

    def test_report_human_and_json(self) -> None:
        write_applied_app(self.tmp_path, "app")
        stack = make_stack(self.tmp_path, (make_app("app"),))
        stats = Stats(stack)
        stats.docker = MagicMock()
        stats.docker.try_service_container_id.return_value = None
        stats.docker.containers_stats.return_value = {}
        with patch(
            "raft.services.stats.service.collect_host_resources",
            return_value=_fake_host(),
        ):
            snap = stats.collect()
        out = StringIO()
        assert write_report(snap, out=out, color=False) == 0
        text = out.getvalue()
        assert "Host" in text
        assert "Containers" in text
        assert "raft-gate" in text
        assert "CPUs: 4" in text

        jout = StringIO()
        assert write_report(snap, as_json=True, out=jout) == 0
        payload = json.loads(jout.getvalue())
        assert payload["host"]["cpus"] == 4
        assert payload["containers"][0]["service"] == "raft-gate"
        assert "allocated" in payload["containers"][0]

        with patch.object(stats, "collect", return_value=snap):
            assert stats.report(as_json=False) == 0

    def test_report_live_and_rejects_json_combo(self) -> None:
        from raft.services.stats.report import overwrite_block, write_live_report

        write_applied_app(self.tmp_path, "app")
        stack = make_stack(self.tmp_path, (make_app("app"),))
        stats = Stats(stack)
        stats.docker = MagicMock()
        stats.docker.try_service_container_id.return_value = None
        stats.docker.containers_stats.return_value = {}
        with patch(
            "raft.services.stats.service.collect_host_resources",
            return_value=_fake_host(),
        ):
            snapshot = stats.collect()

        sleeps: list[float] = []
        out = StringIO()
        collect_calls = {"n": 0}

        def collect():
            collect_calls["n"] += 1
            # First frame must not erase — old content would flash blank.
            if collect_calls["n"] == 1:
                assert out.getvalue() == ""
            return snapshot

        assert (
            write_live_report(
                collect,
                interval=0.01,
                out=out,
                color=False,
                sleep=sleeps.append,
                max_frames=2,
            )
            == 0
        )
        assert collect_calls["n"] == 2
        assert sleeps == [0.01]
        text = out.getvalue()
        assert "Ctrl+C to exit" in text
        # Second frame rewinds only our prior lines, then erases downward.
        assert "\033[" in text and "A\033[G\033[J" in text
        # Full-screen clear must not be used.
        assert "\033[2J" not in text
        assert "\033[H" not in text

        block = StringIO()
        assert overwrite_block(block, "a\nb\n", 0) == 2
        assert overwrite_block(block, "x\n", 2) == 1
        assert block.getvalue().startswith("a\nb\n\033[2A\033[G\033[J")

        with patch.object(stats, "collect", return_value=snapshot):
            with patch(
                "raft.services.stats.service.write_live_report",
                return_value=0,
            ) as live:
                assert stats.report(live=True) == 0
                live.assert_called_once()

        with pytest.raises(OperatorError, match="--json and --live"):
            stats.report(as_json=True, live=True)

    def test_live_keyboard_interrupt(self) -> None:
        from raft.services.stats.models import (
            HostStats,
            StatsSnapshot,
        )
        from raft.services.stats.report import _line_count, write_live_report

        assert _line_count("") == 0
        assert _line_count("one") == 1
        assert _line_count("a\nb\n") == 2

        snap = StatsSnapshot(
            host=HostStats(
                cpus=1,
                loadavg=None,
                memory=None,
                memory_total_bytes=None,
                memory_available_bytes=None,
                disk_path=None,
                disk_total_bytes=None,
                disk_used_bytes=None,
                disk_free_bytes=None,
                disk_used_percent=None,
                uptime_seconds=None,
            ),
            containers=(),
        )
        out = StringIO()
        calls = {"n": 0}

        def sleep(_interval: float) -> None:
            calls["n"] += 1
            raise KeyboardInterrupt

        assert (
            write_live_report(
                lambda: snap,
                out=out,
                color=False,
                sleep=sleep,
            )
            == 0
        )
        assert calls["n"] == 1
        assert out.getvalue().endswith("\n")

    def test_models_to_dict(self) -> None:
        allocated = AllocatedResources("0.5", "128M", "0.1", "32M")
        assert allocated.to_dict()["cpus_limit"] == "0.5"
        from raft.services.stats.models import IoPair, MemoryUsage

        assert IoPair(1, 2).to_dict()["rx_or_read_bytes"] == 1
        assert MemoryUsage(1, 2, 3.0).to_dict()["used_percent"] == 3.0

    def test_inspect_memory_fills_limit_and_bad_pids(self) -> None:
        from raft.services.stats.service import _container_from_row, _pids

        assert _pids(None) is None
        assert _pids("nope") is None
        assert _pids("7") == 7
        row = _container_from_row(
            service="app",
            role="app",
            app="app",
            group=None,
            allocated=AllocatedResources("0.5", "128M", "0.1", "32M"),
            status="running",
            uptime_seconds=10.0,
            stats_row={
                "CPUPerc": "1%",
                "MemUsage": "1MiB / --",
                "MemPerc": "1%",
                "NetIO": "0B / 0B",
                "BlockIO": "0B / 0B",
                "PIDs": "bad",
            },
            inspect_memory=67108864,
        )
        assert row.memory.limit_bytes == 67108864
        assert row.pids is None

    def test_report_degraded_host(self) -> None:
        from raft.services.stats.models import (
            ContainerStats,
            IoPair,
            MemoryUsage,
            StatsSnapshot,
        )
        from raft.services.stats.service import _host_stats

        empty = _host_stats(
            HostResources(
                cpus=None,
                loadavg=None,
                memory=None,
                disk=None,
                uptime_seconds=None,
            )
        )
        assert empty.memory is None
        assert empty.disk_path is None

        snap = StatsSnapshot(
            host=empty,
            containers=(
                ContainerStats(
                    service="app",
                    role="app",
                    app="app",
                    group=None,
                    status="not running",
                    uptime_seconds=None,
                    cpu_percent=None,
                    memory=MemoryUsage(None, None, None),
                    allocated=AllocatedResources("0.5", "", "0.1", "32M"),
                    network=IoPair(None, None),
                    block_io=IoPair(None, None),
                    pids=None,
                ),
                ContainerStats(
                    service="app2",
                    role="app",
                    app="app2",
                    group=None,
                    status="running",
                    uptime_seconds=1.0,
                    cpu_percent=1.0,
                    memory=MemoryUsage(1024, 2048, 50.0),
                    allocated=AllocatedResources("0.5", "128M", "0.1", "32M"),
                    network=IoPair(None, None),
                    block_io=IoPair(None, None),
                    pids=1,
                ),
            ),
        )
        out = StringIO()
        assert write_report(snap, out=out, color=False) == 0
        text = out.getvalue()
        assert "load: -" in text
        assert " / -" in text
        assert "1.0KiB / 2.0KiB" in text



class TestStatsExport:
    def test_lazy_export(self) -> None:
        import raft.services as services

        assert services.Stats is Stats
