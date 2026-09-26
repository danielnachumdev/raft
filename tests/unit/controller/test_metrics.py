"""Batched metrics recorder (controller → state/metrics JSONL)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from raft.controller.metrics import MetricsRecorder
from raft.services.ops.status.models import StatusSnapshot

from ..services.ops.status.fixtures import StatusFixtures
from .base import ControllerTestCase


def _seq_clock(values: List[float]):
    index = {"i": 0}

    def clock() -> float:
        i = min(index["i"], len(values) - 1)
        value = values[i]
        index["i"] += 1
        return value

    return clock


class TestMetricsRecorder(ControllerTestCase):
    def _recorder(
        self,
        home: Path,
        *,
        samples: List[Dict[str, Any]],
        batch_size: int = 10,
        flush_seconds: float = 60.0,
        clock_values: Optional[List[float]] = None,
    ) -> MetricsRecorder:
        remaining = list(samples)
        return MetricsRecorder(
            home,
            batch_size=batch_size,
            flush_seconds=flush_seconds,
            collect_fn=lambda: remaining.pop(0),
            clock=_seq_clock(list(clock_values or [0.0])),
        )

    def test_buffers_until_batch_size(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        rec = self._recorder(
            home,
            samples=[{"host": {"cpus": 1}, "containers": []}] * 3,
            batch_size=3,
            clock_values=[0.0, 1.0, 2.0, 3.0],
        )
        rec.tick()
        rec.tick()
        assert not rec.path.is_file()
        rec.tick()
        lines = rec.path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        row = json.loads(lines[0])
        assert "ts" in row and row["host"]["cpus"] == 1

    def test_flush_on_elapsed_time(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        rec = self._recorder(
            home,
            samples=[{"host": {}, "containers": []}],
            batch_size=10,
            flush_seconds=5.0,
            clock_values=[0.0, 6.0, 6.0],
        )
        rec.tick()
        assert rec.path.is_file()
        assert len(rec.path.read_text(encoding="utf-8").splitlines()) == 1

    def test_flush_noop_when_empty(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        rec = MetricsRecorder(home, collect_fn=lambda: {})
        rec.flush()
        assert not rec.path.is_file()

    def test_preserves_existing_timestamp(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        rec = self._recorder(
            home,
            samples=[{"ts": "fixed", "host": {}, "containers": []}],
            batch_size=1,
            clock_values=[0.0, 0.0],
        )
        rec.tick()
        row = json.loads(rec.path.read_text(encoding="utf-8").strip())
        assert row["ts"] == "fixed"

    def test_collect_status_default_path(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        snap = StatusSnapshot(
            host=StatusFixtures.empty_host_status(),
            containers=(),
        )
        stack = MagicMock(name="loaded_stack")
        with patch("raft.controller.metrics.Stack.load_apps", return_value=stack) as load:
            with patch("raft.controller.metrics.Status") as status_cls:
                status_cls.return_value.collect.return_value = snap
                rec = MetricsRecorder(home, batch_size=1, clock=lambda: 0.0)
                rec.tick()
        load.assert_called_once_with(home)
        status_cls.assert_called_once_with(stack)
        status_cls.return_value.collect.assert_called_once_with()
        row = json.loads(rec.path.read_text(encoding="utf-8").strip())
        assert "host" in row and "containers" in row and "ts" in row

    def test_collect_status_skips_ensure_raft_home(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        snap = StatusSnapshot(
            host=StatusFixtures.empty_host_status(),
            containers=(),
        )
        with patch("raft.controller.metrics.Status") as status_cls:
            status_cls.return_value.collect.return_value = snap
            with patch("raft.models.stack.ensure_raft_home") as ensure:
                MetricsRecorder(home, batch_size=1, clock=lambda: 0.0).tick()
        ensure.assert_not_called()
        status_cls.return_value.collect.assert_called_once_with()

    def test_appends_across_flushes(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        rec = self._recorder(
            home,
            samples=[
                {"host": {"cpus": 1}, "containers": []},
                {"host": {"cpus": 2}, "containers": []},
            ],
            batch_size=1,
            clock_values=[0.0, 1.0, 2.0],
        )
        rec.tick()
        rec.tick()
        lines = rec.path.read_text(encoding="utf-8").strip().splitlines()
        assert [json.loads(line)["host"]["cpus"] for line in lines] == [1, 2]
