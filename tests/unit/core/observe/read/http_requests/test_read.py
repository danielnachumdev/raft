"""Unit tests for HttpRequestsRead + eligibility."""

from pathlib import Path

from raft.core.core.models.state.scaling_store import ScalingStore
from raft.core.core.models.stack import Stack
from raft.core.observe.read.http_requests import HttpRequestsRead
from raft.services.controller.jobs.metrics.http_scrape import (
    ACCESS_LOG_NAME,
    GATE_HTTP_LOG_DIR,
)

from tests.unit.base import AppSpecExtras, AppliedInventory, RaftTestCase


class TestHttpRequestsRead(RaftTestCase):
    def test_eligible_filters_hosts_newest_first(self) -> None:
        stack = self._stack_with_demo()
        self._write_log(
            stack.root,
            "\n".join(
                [
                    '0.01 200 demo-api.test 2026-10-13T01:00:00+00:00 GET /a 192.0.2.10 "A"',
                    '0.02 200 other.test 2026-10-13T01:00:01+00:00 GET /b 192.0.2.11 "B"',
                    '0.03 200 demo-api.test 2026-10-13T01:00:02+00:00 GET /c 192.0.2.12 "C"',
                    "0.04 200 demo-api.test",
                ]
            )
            + "\n",
        )
        payload = HttpRequestsRead(stack).for_service("demo-api", limit=10)
        assert payload["eligible"] is True
        assert len(payload["requests"]) == 3
        # Newest first: legacy line, then /c, then /a (other.test filtered out).
        assert payload["requests"][0]["enriched"] is False
        assert payload["requests"][1]["path"] == "/c"
        assert payload["requests"][2]["path"] == "/a"

    def test_worker_ineligible(self) -> None:
        root = self.tmp_path
        AppliedInventory.write_applied_app(
            root,
            "demo-worker",
            source="docker",
            image="ghcr.io/example/worker",
            public_host="",
            build_context=None,
            extra=AppSpecExtras.worker_ports(),
        )
        stack = Stack.load_apps(root)
        payload = HttpRequestsRead(stack).for_service("demo-worker")
        assert payload["eligible"] is False
        assert payload["requests"] == []

    def test_gate_ineligible(self) -> None:
        stack = self._stack_with_demo()
        payload = HttpRequestsRead(stack).for_service("gate")
        assert payload["eligible"] is False
        assert payload["unknown"] is False

    def test_unknown_service(self) -> None:
        stack = self._stack_with_demo()
        payload = HttpRequestsRead(stack).for_service("missing-app")
        assert payload["unknown"] is True

    def test_scaled_to_zero_flag(self) -> None:
        stack = self._stack_with_demo()
        ScalingStore(stack.root).mark_scaled_to_zero("demo-api")
        payload = HttpRequestsRead(stack).for_service("demo-api")
        assert payload["scaled_to_zero"] is True

    def test_limit_clamp(self) -> None:
        stack = self._stack_with_demo()
        payload = HttpRequestsRead(stack).for_service("demo-api", limit=0)
        assert payload["limit"] == 1

    def _stack_with_demo(self) -> Stack:
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        return Stack.load_apps(self.tmp_path)

    @staticmethod
    def _write_log(root: Path, body: str) -> None:
        path = root / GATE_HTTP_LOG_DIR / ACCESS_LOG_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
