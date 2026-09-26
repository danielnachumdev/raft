"""E2E: scaled-to-zero app serves holding page, wakes, then serves the app."""

from __future__ import annotations

import pytest

from tests.e2e.shared.scale_stack import ScaleE2EStack
from tests.shared.wait import Wait

pytestmark = pytest.mark.e2e


class TestE2EScaleWake:
    def test_holding_page_then_wake(self, isolated_raft_env) -> None:
        with ScaleE2EStack.create(isolated_raft_env) as stack:
            assert "Starting" not in stack.curl_host().body

            stack.scale_to_zero()
            assert "Starting" in stack.curl_host().body

            Wait.until(
                lambda: self._is_live(stack),
                timeout=45.0,
                interval=0.5,
                message="app did not wake from holding-page requests",
            )
            assert "Starting" not in stack.curl_host().body

    @staticmethod
    def _is_live(stack: ScaleE2EStack) -> bool:
        if stack.store.is_scaled_to_zero("http-only"):
            return False
        status, _ = stack.docker.service_runtime("http-only")
        return status == "running"
