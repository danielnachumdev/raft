"""Unit tests for service-log capture + cursor semantics."""

from __future__ import annotations

from pathlib import Path

from raft.core.observe.ops.logs.capture import ServiceLogsCapture
from raft.core.observe.ops.logs.meta import ServiceLogsMeta
from raft.core.observe.ops.logs.store import ServiceLogsStore


class _FakeSource:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.calls: list[tuple[str, str]] = []

    def fetch(self, container: str, *, since: str) -> str:
        self.calls.append((container, since))
        return self.text


class TestServiceLogsCapture:
    def test_ships_new_lines_and_advances_cursor(self, tmp_path: Path) -> None:
        store = ServiceLogsStore(tmp_path, max_age_days=14, max_bytes=1024)
        source = _FakeSource(
            "2026-10-14T12:00:00.000000000Z hello\n"
            "2026-10-14T12:00:01.000000000Z world\n"
        )
        n = ServiceLogsCapture(store, source).ship("demo-api", "cid-aaa")
        assert n == 2
        assert store.active_path("demo-api").read_text(encoding="utf-8") == "hello\nworld\n"
        meta = store.load_meta("demo-api")
        assert meta.container_id == "cid-aaa"
        assert meta.cursor.startswith("2026-10-14T12:00:01")

    def test_skips_lines_at_or_before_cursor(self, tmp_path: Path) -> None:
        store = ServiceLogsStore(tmp_path, max_age_days=14, max_bytes=1024)
        store.save_meta(
            "demo-api",
            ServiceLogsMeta(
                container_id="cid-aaa",
                cursor="2026-10-14T12:00:00.000000000Z",
                generation=0,
            ),
        )
        source = _FakeSource(
            "2026-10-14T12:00:00.000000000Z old\n"
            "2026-10-14T12:00:02.000000000Z new\n"
        )
        n = ServiceLogsCapture(store, source).ship("demo-api", "cid-aaa")
        assert n == 1
        assert store.active_path("demo-api").read_text(encoding="utf-8") == "new\n"

    def test_generation_marker_on_container_change(self, tmp_path: Path) -> None:
        store = ServiceLogsStore(tmp_path, max_age_days=14, max_bytes=1024)
        first = _FakeSource("2026-10-14T12:00:00.000000000Z one\n")
        ServiceLogsCapture(store, first).ship("demo-api", "cid-old")
        second = _FakeSource("2026-10-14T13:00:00.000000000Z two\n")
        ServiceLogsCapture(store, second).ship("demo-api", "cid-new")
        text = store.active_path("demo-api").read_text(encoding="utf-8")
        assert "--- raft: generation container=cid-new" in text
        assert "two" in text
        assert store.load_meta("demo-api").generation == 1

    def test_empty_container_noop(self, tmp_path: Path) -> None:
        store = ServiceLogsStore(tmp_path, max_age_days=14, max_bytes=1024)
        assert ServiceLogsCapture(store, _FakeSource()).ship("demo-api", "") == 0
