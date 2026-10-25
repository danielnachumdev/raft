"""StatusPayloadCache TTL + single-flight coalescing."""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Tuple

import pytest

from raft.core.observe.read.status_payload_cache import StatusPayloadCache


class TestStatusPayloadCache:
    def test_returns_cached_within_ttl(self) -> None:
        clock = _FakeClock(0.0)
        cache = StatusPayloadCache(ttl_seconds=1.0, clock=clock)
        calls: List[int] = []
        loader = _counting_loader(calls)
        assert cache.get_or_load(loader) == {"n": 1}
        clock.now = 0.5
        assert cache.get_or_load(loader) == {"n": 1}
        assert calls == [1]

    def test_reloads_after_ttl(self) -> None:
        clock = _FakeClock(0.0)
        cache = StatusPayloadCache(ttl_seconds=1.0, clock=clock)
        calls: List[int] = []
        loader = _counting_loader(calls)
        assert cache.get_or_load(loader)["n"] == 1
        clock.now = 1.1
        assert cache.get_or_load(loader)["n"] == 2
        assert calls == [1, 1]

    def test_clear_drops_cached_payload(self) -> None:
        cache = StatusPayloadCache(ttl_seconds=10.0)
        assert cache.get_or_load(lambda: {"a": 1}) == {"a": 1}
        cache.clear()
        assert cache.get_or_load(lambda: {"a": 2}) == {"a": 2}

    def test_single_flight_shares_one_loader(self) -> None:
        cache = StatusPayloadCache(ttl_seconds=1.0)
        calls: List[int] = []
        results, errors = _run_paired_flight(
            cache, lambda: _blocking_ok(calls)
        )
        assert errors == []
        assert results == [{"ok": True}, {"ok": True}]
        assert calls == [1]

    def test_flight_error_propagates_to_waiters(self) -> None:
        cache = StatusPayloadCache(ttl_seconds=1.0)
        _results, errors = _run_paired_flight(cache, _blocking_boom)
        assert len(errors) == 2
        assert all(isinstance(exc, RuntimeError) for exc in errors)

    def test_await_flight_without_payload_raises(self) -> None:
        cache = StatusPayloadCache(ttl_seconds=1.0)
        event = threading.Event()
        event.set()
        with pytest.raises(RuntimeError, match="without a payload"):
            cache._await_flight(event, {})


def _counting_loader(calls: List[int]) -> Callable[[], Dict[str, Any]]:
    def loader() -> Dict[str, Any]:
        calls.append(1)
        return {"n": len(calls)}

    return loader


def _blocking_ok(calls: List[int]) -> Dict[str, Any]:
    calls.append(1)
    return {"ok": True}


def _blocking_boom() -> Dict[str, Any]:
    raise RuntimeError("boom")


def _run_paired_flight(
    cache: StatusPayloadCache, body: Callable[[], Dict[str, Any]]
) -> Tuple[List[dict], List[BaseException]]:
    started = threading.Event()
    release = threading.Event()
    loader = _gated_loader(body, started, release)
    results: List[dict] = []
    errors: List[BaseException] = []
    _spawn_pair(lambda: results.append(cache.get_or_load(loader)), errors, started, release)
    return results, errors


def _gated_loader(
    body: Callable[[], Dict[str, Any]],
    started: threading.Event,
    release: threading.Event,
) -> Callable[[], Dict[str, Any]]:
    def loader() -> Dict[str, Any]:
        started.set()
        assert release.wait(timeout=2.0)
        return body()

    return loader


def _spawn_pair(
    work: Callable[[], None],
    errors: List[BaseException],
    started: threading.Event,
    release: threading.Event,
) -> None:
    def worker() -> None:
        try:
            work()
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


class _FakeClock:
    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now
