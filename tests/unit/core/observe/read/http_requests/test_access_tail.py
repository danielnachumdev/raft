"""Unit tests for AccessLogTail byte-window reads."""

from unittest.mock import patch

from raft.core.observe.read.http_requests.access_tail import AccessLogTail

from tests.unit.base import RaftTestCase


class TestAccessLogTail(RaftTestCase):
    def test_missing_file_returns_empty(self) -> None:
        assert AccessLogTail(self.tmp_path / "missing.log").lines() == []

    def test_empty_file_returns_empty(self) -> None:
        path = self.tmp_path / "empty.log"
        path.write_bytes(b"")
        assert AccessLogTail(path).lines() == []

    def test_oserror_returns_empty(self) -> None:
        path = self.tmp_path / "boom.log"
        path.write_text("0.01 200 demo.test\n", encoding="utf-8")
        tail = AccessLogTail(path)
        with patch.object(tail, "_read_tail_bytes", side_effect=OSError("denied")):
            assert tail.lines() == []

    def test_truncates_partial_first_line(self) -> None:
        path = self.tmp_path / "big.log"
        # Prefix junk + newline, then two full lines; max bytes starts mid-junk.
        body = b"PARTIAL" + b"x" * 20 + b"\nkeep-one\nkeep-two\n"
        path.write_bytes(body)
        lines = AccessLogTail(path, max_read_bytes=len(body) - 5).lines()
        assert lines == ["keep-one", "keep-two"]

    def test_window_without_newline_keeps_bytes(self) -> None:
        path = self.tmp_path / "nonl.log"
        path.write_bytes(b"abcdefghij")
        # start > 0 but the window has no \\n — keep the partial chunk.
        assert AccessLogTail(path, max_read_bytes=4).lines() == ["ghij"]

    def test_small_file_keeps_all_lines(self) -> None:
        path = self.tmp_path / "small.log"
        path.write_text("one\n\ntwo\n", encoding="utf-8")
        assert AccessLogTail(path).lines() == ["one", "two"]
