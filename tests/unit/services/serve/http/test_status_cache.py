"""Serve ``/api/status`` short TTL + single-flight coalesce."""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Tuple
from unittest.mock import MagicMock

from raft.core.observe.read.status_payload_cache import StatusPayloadCache
from raft.services.serve.http.page import ServePage

from tests.unit.base import RaftTestCase, StackMakers
from tests.unit.services.serve import fixtures as serve_fx


class TestServeStatusCache(RaftTestCase):
    def test_overlapping_api_status_coalesces_to_one_collect(self) -> None:
        page, calls, started, release = self._blocking_page()
        results, errors = _paired_after_start(page.api_status, started, release)
        assert errors == []
        assert calls["n"] == 1
        assert len(results) == 2
        assert results[0]["apps"] == []
        assert "resources_as_of" in results[0]

    def test_second_poll_within_ttl_skips_collect(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path)
        status = MagicMock()
        status.collect.return_value = serve_fx.empty_snapshot()
        page = ServePage(stack, status=status)
        page._status_cache = StatusPayloadCache(ttl_seconds=30.0)
        assert page.api_status() == page.api_status()
        status.collect.assert_called_once()

    def _blocking_page(
        self,
    ) -> Tuple[ServePage, Dict[str, int], threading.Event, threading.Event]:
        stack = StackMakers.make_stack(self.tmp_path)
        status = MagicMock()
        started = threading.Event()
        release = threading.Event()
        calls = {"n": 0}
        status.collect.side_effect = _make_blocker(calls, started, release)
        page = ServePage(stack, status=status)
        page._status_cache = StatusPayloadCache(ttl_seconds=5.0)
        return page, calls, started, release


def _make_blocker(
    calls: Dict[str, int], started: threading.Event, release: threading.Event
) -> Callable[..., Any]:
    def collect(**_kwargs):
        calls["n"] += 1
        started.set()
        assert release.wait(timeout=2.0)
        return serve_fx.empty_snapshot()

    return collect


def _paired_after_start(
    fn: Callable[[], Any],
    started: threading.Event,
    release: threading.Event,
) -> Tuple[List[Any], List[BaseException]]:
    results: List[Any] = []
    errors: List[BaseException] = []

    def worker() -> None:
        try:
            results.append(fn())
        except BaseException as exc:  # noqa: BLE001 — collect for assert
            errors.append(exc)

    first = threading.Thread(target=worker)
    second = threading.Thread(target=worker)
    first.start()
    assert started.wait(timeout=2.0)
    second.start()
    release.set()
    first.join(timeout=2.0)
    second.join(timeout=2.0)
    return results, errors
