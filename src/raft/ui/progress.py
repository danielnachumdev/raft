"""TTY spinner for long operator commands (stderr; cleared before final output)."""

from __future__ import annotations

import itertools
import sys
import threading
from typing import Optional, TextIO


class TerminalProgress:
    """In-place spinner on a TTY; no-op when redirected / non-interactive."""

    _FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def __init__(
        self,
        stream: Optional[TextIO] = None,
        *,
        prefix: str = "raft",
        label: str = "working",
    ) -> None:
        self._stream = stream if stream is not None else sys.stderr
        self._enabled = bool(getattr(self._stream, "isatty", lambda: False)())
        self._prefix = prefix
        self._default_label = label
        self._label = label
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._frames = itertools.cycle(self._FRAMES)

    def __enter__(self) -> "TerminalProgress":
        if not self._enabled:
            return self
        self._paint()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._enabled:
            self._clear()

    def update(self, label: str) -> None:
        with self._lock:
            self._label = label or self._default_label

    def _spin(self) -> None:
        while not self._stop.wait(0.08):
            self._paint()

    def _paint(self) -> None:
        with self._lock:
            label = self._label
            frame = next(self._frames)
        self._write(f"\r{frame} {self._prefix}: {label}…\033[K")

    def _write(self, text: str) -> None:
        self._stream.write(text)
        self._stream.flush()

    def _clear(self) -> None:
        self._stream.write("\r\033[K")
        self._stream.flush()
