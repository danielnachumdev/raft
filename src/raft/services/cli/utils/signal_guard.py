"""Install SIGINT/SIGTERM handlers for a clean CLI interrupt path."""

import signal
from types import FrameType
from typing import Callable, Optional

from raft.core.platform.adapters.shell.active_child import ActiveShellChild

_HANDLED = (signal.SIGINT, signal.SIGTERM)


class CliSignalGuard:
    """Map SIGINT/SIGTERM to ``KeyboardInterrupt`` after stopping Shell children.

    ``CliExitMapper`` already turns ``KeyboardInterrupt`` into a short
    ``Interrupted.`` message and exit 130. This guard extends that path to
    SIGTERM and ensures in-flight compose/build process groups are terminated
    instead of orphaned.
    """

    def __init__(self) -> None:
        self._previous: dict[int, Callable] = {}

    def __enter__(self) -> "CliSignalGuard":
        for sig in _HANDLED:
            self._previous[sig] = signal.getsignal(sig)
            signal.signal(sig, self._on_signal)
        return self

    def __exit__(self, *_exc) -> None:
        for sig, previous in self._previous.items():
            signal.signal(sig, previous)
        self._previous.clear()

    def _on_signal(self, signum: int, _frame: Optional[FrameType]) -> None:
        ActiveShellChild.terminate_active()
        raise KeyboardInterrupt
