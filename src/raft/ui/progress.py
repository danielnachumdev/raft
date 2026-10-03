"""TTY spinner for long operator commands (stderr; cleared before final output)."""

from __future__ import annotations

import itertools
import sys
import threading
from typing import ClassVar, Optional, TextIO


class TerminalProgress:
    """In-place spinner on a TTY; no-op when redirected / non-interactive.

    Activate with a context manager at the outer stack frame (e.g. CLI entry
    for ``raft doctor`` / ``raft update``). Inner frames update the label via
    ``TerminalProgress.current().update(...)`` / ``.set_text(...)``. Only one
    spinner may be active at a time; ``current()`` raises if none is entered.

    Call ``finish()`` (or ``finish_active()``) before printing final operator
    output so the spinner line is cleared and not overwritten.
    """

    _FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
    _active: ClassVar[Optional["TerminalProgress"]] = None

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
        self._finished = False

    @classmethod
    def current(cls) -> "TerminalProgress":
        """Return the active spinner, or raise if none is entered."""
        if cls._active is None:
            raise RuntimeError(
                "no active TerminalProgress; enter via `with TerminalProgress(...):`"
            )
        return cls._active

    @classmethod
    def active(cls) -> Optional["TerminalProgress"]:
        """Return the active spinner, or ``None`` if none is entered."""
        return cls._active

    @classmethod
    def finish_active(cls) -> None:
        """Stop and clear the active spinner if any (safe before final output)."""
        if cls._active is not None:
            cls._active.finish()

    def __enter__(self) -> "TerminalProgress":
        if TerminalProgress._active is not None:
            raise RuntimeError("TerminalProgress already active; only one spinner at a time")
        TerminalProgress._active = self
        if not self._enabled:
            return self
        self._paint()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.finish()
        if TerminalProgress._active is self:
            TerminalProgress._active = None

    def finish(self) -> None:
        """Stop the spinner thread and clear the line (idempotent)."""
        if self._finished:
            return
        self._finished = True
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._enabled:
            self._clear()

    def update(self, label: str) -> None:
        with self._lock:
            self._label = label or self._default_label

    def set_text(self, label: str) -> None:
        """Alias for ``update`` — preferred name for inner-frame label changes."""
        self.update(label)

    def _spin(self) -> None:
        while not self._stop.wait(0.08):
            self._paint()

    def _paint(self) -> None:
        if self._finished:
            return
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
