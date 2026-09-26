"""E2E: Healer recovers an exited app via Compose, then escalates to redeploy."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.shared.heal_stack import HealE2EStack

pytestmark = pytest.mark.e2e


class TestE2EHeal:
    """Real Docker Compose + Healer (no MagicMock DockerStack).

    Timing (CI-fast; tick(now=) skips wall-clock interval sleep):
      intervalSeconds=1, failThreshold=1, cooldownSeconds=0,
      maxRestarts=1, escalateAfterRestarts=1
    """

    def test_restart_then_escalate(
        self, isolated_raft_env: Path
    ) -> None:
        with HealE2EStack.create(isolated_raft_env) as stack:
            self._assert_restart_recovers(stack)
            self._assert_escalate_after_budget(stack)

    def _assert_restart_recovers(self, stack: HealE2EStack) -> None:
        stack.stop_app()
        stack.healer.tick(now=1.0)
        stack.wait_runtime("running")
        assert stack.healer.restart_counts[stack.APP] == 1
        assert stack.deploy_calls == []

    def _assert_escalate_after_budget(self, stack: HealE2EStack) -> None:
        stack.stop_app()
        stack.healer.tick(now=2.0)
        assert stack.deploy_calls == [stack.APP]
        assert stack.healer.escalate_counts[stack.APP] == 1
        assert stack.healer.restart_counts[stack.APP] == 1
