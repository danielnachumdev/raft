"""Status live-mode report coverage."""

from __future__ import annotations

import json
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch

import pytest

from raft.core.core.config.paths.metrics_paths import MetricsPaths
from raft.core.core.errors.cta import OperatorError
from raft.core.observe.ops.status import Status
from raft.core.observe.ops.status.report import StatusReportWriter
from raft.core.platform.adapters.shell.shell import Shell

from tests.unit.base import AppliedInventory, ShellMocks
from tests.unit.core.observe.ops.status.base import StatusTestCase
from . import fixtures as status_fx

_GATE_INSPECT = json.dumps(
    [
        {
            "Id": "gatecid",
            "State": {"Status": "running", "StartedAt": "2024-01-01T00:00:00Z"},
            "HostConfig": {},
        }
    ]
)
_GATE_STATS = (
    '{"ID":"gatecid","CPUPerc":"1%","MemUsage":"1MiB / 32MiB",'
    '"MemPerc":"1%","NetIO":"0B / 0B","BlockIO":"0B / 0B","PIDs":"1"}\n'
)


class TestStatusReportLive(StatusTestCase):
    def _stopped_snapshot(self):
        status = self.make_status("app")
        status_fx.mock_docker_idle(status)
        with self.patch_host():
            return status, status.collect()

    def test_report_live_and_rejects_json_combo(self) -> None:
        status, snapshot = self._stopped_snapshot()
        self._assert_live_frames(snapshot)
        self._assert_overwrite_block()
        self._assert_status_live_refresh(status, snapshot)
        with pytest.raises(OperatorError, match="--json and --live"):
            status.report(as_json=True, live=True)

    def _assert_live_frames(self, snapshot) -> None:
        sleeps: list[float] = []
        out = StringIO()
        calls = {"n": 0}
        collect = self._frame_collector(calls, out, snapshot)
        code = StatusReportWriter().write_live(
            collect, interval=0.01, out=out, color=False, sleep=sleeps.append, max_frames=2
        )
        assert code == 0
        assert calls["n"] == 2 and sleeps == [0.01]
        self._assert_live_text(out.getvalue())

    @staticmethod
    def _frame_collector(calls, out, snapshot):
        def collect():
            calls["n"] += 1
            if calls["n"] == 1:
                assert out.getvalue() == ""
            return snapshot

        return collect

    @staticmethod
    def _assert_live_text(text: str) -> None:
        assert "Ctrl+C to exit" in text
        assert "\033[" in text and "A\033[G\033[J" in text
        assert "\033[2J" not in text and "\033[H" not in text

    def _assert_overwrite_block(self) -> None:
        writer = StatusReportWriter()
        block = StringIO()
        assert writer.overwrite_block(block, "a\nb\n", 0) == 2
        assert writer.overwrite_block(block, "x\n", 2) == 1
        assert block.getvalue().startswith("a\nb\n\033[2A\033[G\033[J")

    def _assert_status_live_refresh(self, status, snapshot) -> None:
        with patch.object(status, "collect", return_value=snapshot):
            with patch.object(StatusReportWriter, "write_live", return_value=0) as live:
                assert status.report(live=True) == 0
                live.assert_called_once()
                frame_collect = live.call_args.args[0]
                with patch.object(status, "collect", return_value=snapshot) as collect:
                    frame_collect()
                collect.assert_called_once_with(
                    refresh_apps=True, include_stats=True
                )

    def test_collect_refresh_apps_reloads_registry(self) -> None:
        status = self.make_status("app")
        status_fx.mock_docker_idle(status)
        AppliedInventory.write_applied_app(self.tmp_path, "newbie")
        with self.patch_host():
            snap = status.collect(refresh_apps=True)
        names = [c.service for c in snap.containers]
        assert "app" in names and "newbie" in names
        assert len(status.stack.apps) == 2

    def test_default_report_skips_docker_stats_live_calls_it(self) -> None:
        status = self.make_status("app")
        commands: list[str] = []
        self._write_gate_sample()
        with patch.object(Shell, "docker", self._recording_docker(commands)):
            with self.patch_host(), self._demo_host_identity():
                payload = self._report_json(status)
        gate = next(row for row in payload["containers"] if row["service"] == "raft-gate")
        assert gate["cpu_percent"] == 4.25
        assert "memory" in gate and "host" in payload
        assert "stats" not in commands
        commands.clear()
        with patch.object(Shell, "docker", self._recording_docker(commands)):
            with self.patch_host(), self._demo_host_identity():
                with patch.object(StatusReportWriter, "write_live", return_value=0) as live:
                    assert status.report(live=True) == 0
                    live.call_args.args[0]()
        assert "stats" in commands

    def _report_json(self, status: Status) -> dict:
        buf = StringIO()
        with redirect_stdout(buf):
            assert status.report(as_json=True) == 0
        return json.loads(buf.getvalue())

    def _write_gate_sample(self) -> None:
        path = MetricsPaths(self.tmp_path).resources()
        path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat()
        path.write_text(
            '{"ts":"%s","containers":[{"service":"raft-gate","cpu_percent":4.25,'
            '"memory":{"used_percent":9.0}}]}\n' % ts,
            encoding="utf-8",
        )

    @staticmethod
    def _recording_docker(commands: list[str]):
        def docker(_shell: Shell, *args: str, **_kwargs: object):
            commands.append(args[0] if args else "")
            return TestStatusReportLive._docker_reply(args)

        return docker

    @staticmethod
    def _docker_reply(args: tuple[str, ...]):
        if args[:1] == ("ps",):
            return ShellMocks.completed(stdout="gatecid\traft-gate\n")
        if args[:1] == ("inspect",):
            return ShellMocks.completed(stdout=_GATE_INSPECT)
        if args[:1] == ("stats",):
            return ShellMocks.completed(stdout=_GATE_STATS)
        return ShellMocks.completed()

    @staticmethod
    def _demo_host_identity():
        return patch.multiple(
            "raft.core.observe.ops.status.service.HostGateway",
            hostname=lambda self: "demo-host",
            fqdn=lambda self: None,
        )

    def test_live_keyboard_interrupt(self) -> None:
        writer = StatusReportWriter()
        assert writer._line_count("") == 0
        assert writer._line_count("one") == 1
        assert writer._line_count("a\nb\n") == 2
        snap = status_fx.snapshot()
        out = StringIO()
        calls = {"n": 0}

        def sleep(_interval: float) -> None:
            calls["n"] += 1
            raise KeyboardInterrupt

        assert writer.write_live(lambda: snap, out=out, color=False, sleep=sleep) == 0
        assert calls["n"] == 1
        assert out.getvalue().endswith("\n")
