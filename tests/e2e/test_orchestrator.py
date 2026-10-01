"""E2E: JobOrchestrator schedules heal/metrics independently and nudges metrics on heal."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.shared.orch_stack import (
    HEAL_INTERVAL,
    METRICS_INTERVAL,
    OrchE2EStack,
)

pytestmark = pytest.mark.e2e


class TestE2EOrchestrator:
    """Real Docker + JobOrchestrator with a virtual clock (not wall-time sleeps).

    Scenario:
      1) Cadence — heal every 10s, metrics every 60s: by t≈45s heal has fired
         several times while metrics only once (t=0).
      2) Nudge — stop the app in the metrics gap; next heal recovers it and
         enqueues a one-shot metrics job (extra sample before t=60).
      3) Schedule intact — the next *periodic* metrics fire still lands at 60s.
    """

    def test_heal_metrics_cadence_and_nudge(self, isolated_raft_env: Path) -> None:
        with OrchE2EStack.create(isolated_raft_env) as stack:
            self._assert_independent_cadence(stack)
            self._assert_heal_nudges_metrics(stack)
            self._assert_periodic_metrics_still_on_schedule(stack)

    def _assert_independent_cadence(self, stack: OrchE2EStack) -> None:
        # First fires ASAP (t=0); then heal at 10/20/30/40; metrics next at 60.
        target = HEAL_INTERVAL * 4.5
        stack.run_until(lambda: stack.clock.elapsed >= target)
        assert len(stack.heal_fires) >= 5  # 0,10,20,30,40
        assert stack.metrics_fires == [0.0]
        assert all(
            abs(stack.heal_fires[i] - HEAL_INTERVAL * i) < 0.01
            for i in range(min(5, len(stack.heal_fires)))
        )

    def _assert_heal_nudges_metrics(self, stack: OrchE2EStack) -> None:
        stack.stop_app()
        before = len(stack.metrics_fires)
        # Next heal due at 50s; one-shot metrics must run in that cycle.
        stack.run_until(lambda: len(stack.metrics_fires) > before)
        stack.wait_runtime("running")
        assert stack.healer.restart_counts[stack.APP] == 1
        assert len(stack.metrics_fires) == before + 1
        nudged_at = stack.metrics_fires[-1]
        assert nudged_at < METRICS_INTERVAL
        assert nudged_at >= HEAL_INTERVAL * 5  # ~50s heal slot

    def _assert_periodic_metrics_still_on_schedule(self, stack: OrchE2EStack) -> None:
        before = len(stack.metrics_fires)
        stack.run_until(lambda: len(stack.metrics_fires) > before)
        # One-shot must not have advanced the periodic schedule past 60s.
        assert stack.metrics_fires[-1] == pytest.approx(METRICS_INTERVAL, abs=0.01)
        assert len(stack.metrics_fires) == before + 1
