"""Host CLI log file retention: age + size, oldest first."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from raft.config.log_retention import LogRetention


class TestLogRetention:
    def _line(self, when: datetime, msg: str) -> str:
        return f"{when.strftime('%Y-%m-%d %H:%M:%S')} INFO [raft.test] {msg}"

    def _write(self, path: Path, lines: list[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")

    def test_drops_old_lines_by_age(self, tmp_path: Path) -> None:
        path = tmp_path / "raft.log"
        now = datetime(2026, 6, 1, 12, 0, 0)
        self._write(
            path,
            [
                self._line(now - timedelta(days=40), "ancient"),
                self._line(now - timedelta(days=1), "fresh"),
            ],
        )
        LogRetention(max_age_days=30, max_bytes=10_000_000, wall_clock=lambda: now).prune(
            path
        )
        text = path.read_text(encoding="utf-8")
        assert "ancient" not in text
        assert "fresh" in text

    def test_trims_oldest_when_over_max_bytes(self, tmp_path: Path) -> None:
        path = tmp_path / "raft.log"
        now = datetime(2026, 6, 1, 12, 0, 0)
        lines = [
            self._line(now, "one-xxxx"),
            self._line(now, "two-xxxx"),
            self._line(now, "three-xx"),
        ]
        self._write(path, lines)
        # Force dropping at least the first line.
        max_bytes = sum(len(line) + 1 for line in lines[1:])
        LogRetention(max_age_days=30, max_bytes=max_bytes, wall_clock=lambda: now).prune(
            path
        )
        kept = path.read_text(encoding="utf-8").splitlines()
        assert kept
        assert "one-xxxx" not in kept[0]
        assert path.stat().st_size <= max_bytes

    def test_noop_when_missing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "missing.log"
        LogRetention(max_age_days=30, max_bytes=100).prune(path)
        assert not path.exists()

    def test_unparseable_prefix_treated_as_ancient(self, tmp_path: Path) -> None:
        path = tmp_path / "raft.log"
        now = datetime(2026, 6, 1, 12, 0, 0)
        path.write_text(
            "\nnot-a-log-line\n"
            + "short\n"
            + "XXXXXXXXXXXXXXXXXXX bad-prefix\n"
            + self._line(now, "kept")
            + "\n",
            encoding="utf-8",
        )
        LogRetention(max_age_days=30, max_bytes=10_000_000, wall_clock=lambda: now).prune(
            path
        )
        text = path.read_text(encoding="utf-8")
        assert "not-a-log-line" not in text
        assert "short" not in text
        assert "bad-prefix" not in text
        assert "kept" in text

    def test_skips_when_max_bytes_non_positive(self, tmp_path: Path) -> None:
        path = tmp_path / "raft.log"
        path.write_text(
            self._line(datetime(2026, 6, 1), "stay") + "\n",
            encoding="utf-8",
        )
        LogRetention(max_age_days=30, max_bytes=0).prune(path)
        assert "stay" in path.read_text(encoding="utf-8")
