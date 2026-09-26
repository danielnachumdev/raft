"""E2E: scaled-to-zero app serves holding page, wakes, then serves the app."""

from __future__ import annotations

import time

import pytest

from tests.e2e.shared.scale_stack import ScaleE2EStack

pytestmark = pytest.mark.e2e


class TestE2EScaleWake:
    def test_holding_page_then_wake(self, isolated_raft_env) -> None:
        with ScaleE2EStack.create(isolated_raft_env) as stack:
            status, body = stack.curl_host()
            assert status == 200
            assert "Starting" not in body

            stack.scale_to_zero()
            status, body = stack.curl_host()
            assert status == 200
            assert "Starting" in body

            self._wait_awake(stack)
            status, body = stack.curl_host()
            assert status == 200
            assert "Starting" not in body

    def _wait_awake(self, stack: ScaleE2EStack, *, timeout: float = 45.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._is_live(stack):
                return
            time.sleep(0.5)
        raise TimeoutError("app did not wake from holding-page requests")

    @staticmethod
    def _is_live(stack: ScaleE2EStack) -> bool:
        if stack.store.is_scaled_to_zero("http-only"):
            return False
        status, _ = stack.docker.service_runtime("http-only")
        return status == "running"
