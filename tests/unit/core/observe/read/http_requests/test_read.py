"""Unit tests for HttpRequestsRead + eligibility."""

from pathlib import Path
from unittest.mock import patch

from raft.core.core.models.app import App
from raft.core.core.models.state.scaling_store import ScalingStore
from raft.core.core.models.stack import Stack
from raft.core.observe.read.http_requests import HttpRequestsRead, MAX_LIMIT
from raft.core.observe.read.http_requests.eligibility import HttpRequestsEligibility
from raft.services.controller.jobs.metrics.http_scrape import (
    ACCESS_LOG_NAME,
    GATE_HTTP_LOG_DIR,
)

from tests.unit.base import AppSpecExtras, AppliedInventory, RaftTestCase


class TestHttpRequestsRead(RaftTestCase):
    def test_eligible_filters_hosts_newest_first(self) -> None:
        stack = self._stack_with_demo()
        self._write_log(stack.root, self._mixed_host_access_log())
        payload = HttpRequestsRead(stack).for_service("demo-api", limit=10)
        assert payload["eligible"] is True
        assert len(payload["requests"]) == 3
        assert payload["requests"][0]["path"] == "/d"
        assert payload["requests"][1]["path"] == "/c"
        assert payload["requests"][2]["path"] == "/a"

    @staticmethod
    def _mixed_host_access_log() -> str:
        return (
            "\n".join(
                [
                    '0.01 200 demo-api.test 2026-10-13T01:00:00+00:00 GET /a 192.0.2.10 "A"',
                    '0.02 200 other.test 2026-10-13T01:00:01+00:00 GET /b 192.0.2.11 "B"',
                    '0.03 200 demo-api.test 2026-10-13T01:00:02+00:00 GET /c 192.0.2.12 "C"',
                    '0.04 200 demo-api.test 2026-10-13T01:00:03+00:00 GET /d 192.0.2.13 "D"',
                    "0.05 200 demo-api.test",  # short non-matching line; skipped
                ]
            )
            + "\n"
        )

    def test_worker_ineligible(self) -> None:
        stack = self._worker_stack()
        payload = HttpRequestsRead(stack).for_service("demo-worker")
        assert payload["eligible"] is False
        assert payload["requests"] == []

    def test_http_without_public_host_ineligible(self) -> None:
        # Registry rejects empty publicHost + expose:http; exercise App-level check.
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        app = App(name="demo-api", public_host="", source="local", path="services/demo-api/checkout")
        stack = Stack(root=self.tmp_path, apps=(app,))
        target = HttpRequestsEligibility(stack).resolve("demo-api")
        assert target.eligible is False
        assert "publicHost" in (target.reason or "")

    def test_spec_load_failure_ineligible(self) -> None:
        stack = self._stack_with_demo()
        with patch.object(Stack, "spec_for", side_effect=RuntimeError("bad yaml")):
            target = HttpRequestsEligibility(stack).resolve("demo-api")
        assert target.eligible is False
        assert "could not load" in (target.reason or "")

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

    def test_scaled_to_zero_still_returns_history(self) -> None:
        stack = self._stack_with_demo()
        ScalingStore(stack.root).mark_scaled_to_zero("demo-api")
        self._write_log(
            stack.root,
            '0.01 200 demo-api.test 2026-10-13T01:00:00+00:00 GET /past '
            '192.0.2.10 "DemoAgent/1.0"\n'
            '0.02 200 demo-api.test 2026-10-13T01:00:01+00:00 GET '
            '/_raft_hold_demo-api 192.0.2.11 "DemoAgent/1.0"\n',
        )
        payload = HttpRequestsRead(stack).for_service("demo-api", limit=10)
        assert payload["eligible"] is True
        assert payload["scaled_to_zero"] is True
        assert payload["reason"] is None
        assert [row["path"] for row in payload["requests"]] == [
            "/_raft_hold_demo-api",
            "/past",
        ]

    def test_scaled_to_zero_empty_history_still_eligible(self) -> None:
        stack = self._stack_with_demo()
        ScalingStore(stack.root).mark_scaled_to_zero("demo-api")
        payload = HttpRequestsRead(stack).for_service("demo-api")
        assert payload["eligible"] is True
        assert payload["scaled_to_zero"] is True
        assert payload["requests"] == []

    def test_compose_id_lookup_when_scaled_to_zero(self) -> None:
        stack = self._stack_with_demo()
        app = stack.apps[0]
        ScalingStore(stack.root).mark_scaled_to_zero(app.name)
        self._write_log(
            stack.root,
            '0.01 200 demo-api.test 2026-10-13T01:00:00+00:00 GET /via-id '
            '192.0.2.10 "DemoAgent/1.0"\n',
        )
        payload = HttpRequestsRead(stack).for_service(app.compose_id)
        assert payload["eligible"] is True
        assert payload["requests"][0]["path"] == "/via-id"

    def test_limit_clamp_min_and_max(self) -> None:
        stack = self._stack_with_demo()
        low = HttpRequestsRead(stack).for_service("demo-api", limit=0)
        high = HttpRequestsRead(stack).for_service("demo-api", limit=MAX_LIMIT + 50)
        assert low["limit"] == 1
        assert high["limit"] == MAX_LIMIT

    def test_bind_stack_updates_log_path(self) -> None:
        first = self._stack_with_demo()
        reader = HttpRequestsRead(first)
        other_root = self.tmp_path / "other-home"
        AppliedInventory.write_applied_app(
            other_root, "demo-api", public_host="demo-api.test"
        )
        second = Stack.load_apps(other_root)
        reader.bind_stack(second)
        assert reader.stack is second

    def _stack_with_demo(self) -> Stack:
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        return Stack.load_apps(self.tmp_path)

    def _worker_stack(self) -> Stack:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "demo-worker",
            source="docker",
            image="ghcr.io/example/worker",
            public_host="",
            build_context=None,
            extra=AppSpecExtras.worker_ports(),
        )
        return Stack.load_apps(self.tmp_path)

    @staticmethod
    def _write_log(root: Path, body: str) -> None:
        path = root / GATE_HTTP_LOG_DIR / ACCESS_LOG_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
