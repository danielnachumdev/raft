"""CrashLoopDetector Engine-fact heuristic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from raft.adapters.docker.crash_loop import CrashLoopDetector


class TestCrashLoopDetector:
    def test_running_with_high_restarts_and_short_uptime(self) -> None:
        assert CrashLoopDetector.is_crash_looping(
            status="running",
            restart_count=3,
            uptime_seconds=120.0,
            oom_killed=False,
        )

    def test_recovered_high_restarts_long_uptime(self) -> None:
        assert not CrashLoopDetector.is_crash_looping(
            status="running",
            restart_count=50,
            uptime_seconds=3600.0,
            oom_killed=False,
        )

    def test_below_restart_threshold(self) -> None:
        assert not CrashLoopDetector.is_crash_looping(
            status="running",
            restart_count=2,
            uptime_seconds=30.0,
            oom_killed=False,
        )

    def test_oom_killed_alone(self) -> None:
        assert CrashLoopDetector.is_crash_looping(
            status="running",
            restart_count=0,
            uptime_seconds=3600.0,
            oom_killed=True,
        )

    def test_restarting_status(self) -> None:
        assert CrashLoopDetector.is_crash_looping(
            status="restarting",
            restart_count=0,
            uptime_seconds=None,
            oom_killed=False,
        )

    def test_missing_uptime_with_restarts(self) -> None:
        assert not CrashLoopDetector.is_crash_looping(
            status="running",
            restart_count=10,
            uptime_seconds=None,
            oom_killed=False,
        )

    def test_uptime_seconds_parse(self) -> None:
        started = datetime.now(timezone.utc) - timedelta(minutes=5)
        secs = CrashLoopDetector.uptime_seconds(
            started.isoformat().replace("+00:00", "Z")
        )
        assert secs is not None
        assert 290 <= secs <= 320
        assert CrashLoopDetector.uptime_seconds("") is None
        assert CrashLoopDetector.uptime_seconds("0001-01-01T00:00:00Z") is None
        assert CrashLoopDetector.uptime_seconds("not-a-date") is None

    def test_detail_and_fix(self) -> None:
        detail = CrashLoopDetector.detail(
            restart_count=629, uptime_seconds=90.0, oom_killed=False
        )
        assert "crash-looping" in detail
        assert "629" in detail
        assert "heuristic" in detail
        oom = CrashLoopDetector.detail(
            restart_count=1, uptime_seconds=10.0, oom_killed=True
        )
        assert "OOMKilled" in oom
        fix = CrashLoopDetector.fix_cta("raft-controller")
        assert "raft-controller" in fix
        assert "RestartCount" in fix
