"""Retention rotation + offline reader for service logs."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from raft.core.core.utils import LogRotationBootstrap
from raft.core.observe.ops.logs.reader import ServiceLogsReader
from raft.core.observe.ops.logs.store import ServiceLogsStore


class TestServiceLogsStoreReader:
    def test_reader_tails_across_sealed_archives(self, tmp_path: Path) -> None:
        store = ServiceLogsStore(tmp_path, max_age_days=30, max_bytes=10_000_000)
        active = store.active_path("demo-api")
        active.parent.mkdir(parents=True)
        sealed = active.parent / "current.log.2026-10-13"
        sealed.write_text("old-a\nold-b\n", encoding="utf-8")
        active.write_text("new-a\nnew-b\nnew-c\n", encoding="utf-8")
        text = ServiceLogsReader(store).tail("demo-api", lines=3)
        assert text == "new-a\nnew-b\nnew-c"
        text2 = ServiceLogsReader(store).tail("demo-api", lines=4)
        assert text2 == "old-b\nnew-a\nnew-b\nnew-c"

    def test_rotation_seals_oversized_active(self, tmp_path: Path) -> None:
        store = ServiceLogsStore(
            tmp_path,
            max_age_days=14,
            max_bytes=100,
            rotation=LogRotationBootstrap(
                max_age_days=14,
                max_bytes=100,
                wall_clock=lambda: datetime(2026, 10, 14, 12, 0, 0),
            ),
        )
        payload = "x" * 200
        active = store.active_path("demo-api")
        active.parent.mkdir(parents=True)
        active.write_text(payload, encoding="utf-8")
        now = datetime(2026, 10, 14, 12, 0, 0)
        os.utime(active, (now.timestamp(), now.timestamp()))
        store.append_lines("demo-api", ["fresh"])
        assert "fresh" in active.read_text(encoding="utf-8")
        sealed = list(active.parent.glob("current.log.2026-10-14*"))
        assert sealed and sealed[0].read_text(encoding="utf-8") == payload

    def test_empty_reader(self, tmp_path: Path) -> None:
        store = ServiceLogsStore(tmp_path, max_age_days=14, max_bytes=1024)
        assert ServiceLogsReader(store).tail("demo-api", lines=10) == ""
        assert ServiceLogsReader(store).tail("demo-api", lines=0) == ""

    def test_reader_file_starting_with_newline(self, tmp_path: Path) -> None:
        store = ServiceLogsStore(tmp_path, max_age_days=14, max_bytes=1024)
        active = store.active_path("demo-api")
        active.parent.mkdir(parents=True)
        # Leading newline leaves an empty remainder after reverse split.
        active.write_text("\nonly\n", encoding="utf-8")
        assert ServiceLogsReader(store).tail("demo-api", lines=5) == "only"
