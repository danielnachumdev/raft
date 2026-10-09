"""Batched HTTP metrics recorder → state/metrics/http.jsonl."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from raft.controller.http_metrics import HttpMetricsRecorder

from .base import ControllerTestCase


def _seq_clock(values: List[float]):
    index = {"i": 0}

    def clock() -> float:
        i = min(index["i"], len(values) - 1)
        value = values[i]
        index["i"] += 1
        return value

    return clock


class TestHttpMetricsRecorder(ControllerTestCase):
    def _recorder(
        self,
        home: Path,
        *,
        samples: List[Dict[str, Any]],
        batch_size: int = 10,
        flush_seconds: float = 60.0,
        clock_values: Optional[List[float]] = None,
    ) -> HttpMetricsRecorder:
        remaining = list(samples)
        return HttpMetricsRecorder(
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
            samples=[{"requests": 1, "rps": 1.0}] * 3,
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
        assert "ts" in row and row["requests"] == 1

    def test_flush_noop_when_empty(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        HttpMetricsRecorder(home, collect_fn=lambda: {}).flush()
        assert not (home / "state" / "metrics" / "http.jsonl").is_file()

    def test_flush_on_elapsed_time(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        rec = self._recorder(
            home,
            samples=[{"requests": 1}],
            batch_size=10,
            flush_seconds=5.0,
            clock_values=[0.0, 6.0, 6.0],
        )
        rec.tick()
        assert rec.path.is_file()

    def test_uses_scraper_when_no_collect_fn(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        scraper = MagicMock()
        scraper.sample.return_value = {"requests": 0, "rps": 0.0}
        rec = HttpMetricsRecorder(
            home, batch_size=1, scraper=scraper, clock=lambda: 0.0
        )
        rec.tick()
        scraper.sample.assert_called_once()
        assert rec.path.is_file()

    def test_permission_denied_logs_and_reraises(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        home = self.raft_home(tmp_path)
        rec = self._recorder(
            home,
            samples=[{"requests": 1}],
            batch_size=1,
            clock_values=[0.0, 0.0],
        )
        rec.path.parent.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(Path, "open", lambda *a, **k: (_ for _ in ()).throw(PermissionError("x")))
        with patch("raft.controller.http_metrics.logger") as log:
            raised = False
            try:
                rec.tick()
            except PermissionError:
                raised = True
            assert raised
            log.error.assert_called_once()
