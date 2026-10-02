"""Shared TTY spinner used by doctor, update, and other long ops."""

from __future__ import annotations

import io
import time

from raft.ui.progress import TerminalProgress


class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


class _NoTty(io.StringIO):
    def isatty(self) -> bool:
        return False


class TestTerminalProgress:
    def test_spinner_noop_when_not_tty(self) -> None:
        stream = _NoTty()
        with TerminalProgress(stream, prefix="raft doctor") as progress:
            progress.update("host")
        assert stream.getvalue() == ""

    def test_spinner_noop_when_stream_lacks_isatty(self) -> None:
        class _Bare:
            def __init__(self) -> None:
                self.buf: list[str] = []

            def write(self, text: str) -> None:
                self.buf.append(text)

            def flush(self) -> None:
                return None

        stream = _Bare()
        with TerminalProgress(stream, prefix="raft doctor") as progress:
            progress.update("host")
        assert stream.buf == []

    def test_spinner_writes_and_clears_on_tty(self) -> None:
        stream = _Tty()
        with TerminalProgress(stream, prefix="raft doctor", label="checking") as progress:
            progress.update("")
            time.sleep(0.2)
        text = stream.getvalue()
        assert "raft doctor:" in text
        assert "\033[K" in text

    def test_paint_clears_eol_when_label_shortens(self) -> None:
        stream = _Tty()
        progress = TerminalProgress(stream, prefix="raft doctor", label="checking")
        progress.update("runtime")
        progress._paint()
        progress.update("edge")
        progress._paint()
        visible = self._visible_line(stream.getvalue())
        assert "raft doctor: edge…" in visible
        assert "me…" not in visible
        assert visible.endswith("…")

    def test_update_prefix_label(self) -> None:
        stream = _Tty()
        progress = TerminalProgress(stream, prefix="raft update", label="updating")
        progress._paint()
        assert "raft update: updating…" in stream.getvalue()

    @staticmethod
    def _visible_line(raw: str) -> str:
        buf: list[str] = []
        col = 0
        i = 0
        while i < len(raw):
            if raw.startswith("\r", i):
                col = 0
                i += 1
                continue
            if raw.startswith("\033[K", i):
                del buf[col:]
                i += 3
                continue
            if col < len(buf):
                buf[col] = raw[i]
            else:
                buf.append(raw[i])
            col += 1
            i += 1
        return "".join(buf)
