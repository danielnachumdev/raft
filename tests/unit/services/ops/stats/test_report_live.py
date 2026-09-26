"""Stats live-mode report coverage."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest

from raft.errors import OperatorError
from raft.services.ops.stats import Stats
from raft.services.ops.stats.report import overwrite_block, write_live_report

from ....base import RaftTestCase, make_app, make_stack, write_applied_app
from .fixtures import StatsFixtures


class TestStatsReportLive(RaftTestCase):
    def _stopped_snapshot(self):
        write_applied_app(self.tmp_path, "app")
        stats = Stats(make_stack(self.tmp_path, (make_app("app"),)))
        StatsFixtures.mock_docker_idle(stats)
        with patch(
            "raft.services.ops.stats.service.collect_host_resources",
            return_value=StatsFixtures.host(),
        ):
            return stats, stats.collect()

    def test_report_live_and_rejects_json_combo(self) -> None:
        stats, snapshot = self._stopped_snapshot()
        self._assert_live_frames(snapshot)
        self._assert_overwrite_block()
        self._assert_stats_live_refresh(stats, snapshot)
        with pytest.raises(OperatorError, match="--json and --live"):
            stats.report(as_json=True, live=True)

    def _assert_live_frames(self, snapshot) -> None:
        sleeps: list[float] = []
        out = StringIO()
        calls = {"n": 0}

        def collect():
            calls["n"] += 1
            if calls["n"] == 1:
                assert out.getvalue() == ""
            return snapshot

        assert write_live_report(
            collect, interval=0.01, out=out, color=False, sleep=sleeps.append, max_frames=2
        ) == 0
        assert calls["n"] == 2 and sleeps == [0.01]
        text = out.getvalue()
        assert "Ctrl+C to exit" in text
        assert "\033[" in text and "A\033[G\033[J" in text
        assert "\033[2J" not in text and "\033[H" not in text

    def _assert_overwrite_block(self) -> None:
        block = StringIO()
        assert overwrite_block(block, "a\nb\n", 0) == 2
        assert overwrite_block(block, "x\n", 2) == 1
        assert block.getvalue().startswith("a\nb\n\033[2A\033[G\033[J")

    def _assert_stats_live_refresh(self, stats, snapshot) -> None:
        with patch.object(stats, "collect", return_value=snapshot):
            with patch(
                "raft.services.ops.stats.service.write_live_report", return_value=0
            ) as live:
                assert stats.report(live=True) == 0
                live.assert_called_once()
                frame_collect = live.call_args.args[0]
                with patch.object(stats, "collect", return_value=snapshot) as collect:
                    frame_collect()
                collect.assert_called_once_with(refresh_apps=True)

    def test_collect_refresh_apps_reloads_registry(self) -> None:
        write_applied_app(self.tmp_path, "app")
        stats = Stats(make_stack(self.tmp_path, (make_app("app"),)))
        StatsFixtures.mock_docker_idle(stats)
        write_applied_app(self.tmp_path, "newbie")
        with patch(
            "raft.services.ops.stats.service.collect_host_resources",
            return_value=StatsFixtures.host(),
        ):
            snap = stats.collect(refresh_apps=True)
        names = [c.service for c in snap.containers]
        assert "app" in names and "newbie" in names
        assert len(stats.stack.apps) == 2

    def test_live_keyboard_interrupt(self) -> None:
        from raft.services.ops.stats.report import _line_count

        assert _line_count("") == 0
        assert _line_count("one") == 1
        assert _line_count("a\nb\n") == 2
        snap = StatsFixtures.snapshot()
        out = StringIO()
        calls = {"n": 0}

        def sleep(_interval: float) -> None:
            calls["n"] += 1
            raise KeyboardInterrupt

        assert write_live_report(lambda: snap, out=out, color=False, sleep=sleep) == 0
        assert calls["n"] == 1
        assert out.getvalue().endswith("\n")
