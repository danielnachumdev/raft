"""E2E: wake timeout page shows admin CTA and the server-minted id."""

from __future__ import annotations

import logging

import pytest

from tests.e2e.shared.scale_stack import APP, SCALING, ScaleE2EStack

pytestmark = pytest.mark.e2e


class TestE2EScaleTimeoutPage:
    def test_timeout_page_id_matches_controller_log(self, isolated_raft_env, caplog) -> None:
        with ScaleE2EStack.create(isolated_raft_env) as stack:
            stack.scale_to_zero()
            self._stub_wake(stack)
            hold = stack.curl_host().body
            assert "Just a moment" in hold
            assert "contact the administrator" not in hold
            wake_id = self._expire_wake(stack, caplog)
            html = stack.curl_host().body
            assert "contact the administrator" in html
            assert wake_id in html
            assert "Just a moment" not in html

    @staticmethod
    def _stub_wake(stack: ScaleE2EStack) -> None:
        stack.scaler.request_wake = lambda name: None  # noqa: ARG005

    def _expire_wake(self, stack: ScaleE2EStack, caplog) -> str:
        wake_id = stack.store.request_wake(APP, now=0.0)
        assert wake_id
        with caplog.at_level(logging.WARNING):
            stack.scaler.tick(now=float(SCALING["wakeTimeoutSeconds"]) + 1.0)
        assert stack.store.load(APP).wake_timed_out is True
        assert f"id={wake_id}" in caplog.text
        self._stub_wake(stack)
        return wake_id
