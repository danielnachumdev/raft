"""Doctor run observability — suite timings and compose amplification."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ComposeCallCounter:
    """Count ``Shell.compose`` invocations for one doctor run."""

    def __init__(self) -> None:
        self.total = 0
        self.ps = 0
        self._restores: list[Callable[[], None]] = []

    def install(self, *shells: Any) -> None:
        seen: set[int] = set()
        for shell in shells:
            self._install_one(shell, seen)

    def uninstall(self) -> None:
        while self._restores:
            self._restores.pop()()

    def log_summary(self) -> None:
        logger.info("doctor compose calls total=%s ps=%s", self.total, self.ps)

    def _install_one(self, shell: Any, seen: set[int]) -> None:
        if shell is None or id(shell) in seen:
            return
        if not callable(getattr(shell, "compose", None)):
            return
        seen.add(id(shell))
        self._wrap(shell)

    def _wrap(self, shell: Any) -> None:
        original = shell.compose

        def compose(*args: str, **kwargs: Any) -> Any:
            self._note(*args)
            return original(*args, **kwargs)

        shell.compose = compose
        self._restores.append(_ComposeRestore(shell, original))

    def _note(self, *args: str) -> None:
        self.total += 1
        if args and args[0] == "ps":
            self.ps += 1


class _ComposeRestore:
    """Restore ``shell.compose`` after a doctor run."""

    def __init__(self, shell: Any, original: Callable[..., Any]) -> None:
        self._shell = shell
        self._original = original

    def __call__(self) -> None:
        self._shell.compose = self._original


class SuiteTiming:
    """INFO start/done spans for one check suite."""

    def __init__(self, name: str, *, clock: Optional[Callable[[], float]] = None) -> None:
        self.name = name
        self._clock = clock or time.perf_counter
        self._started = 0.0

    def start(self) -> None:
        self._started = self._clock()
        logger.info("doctor suite start name=%s", self.name)

    def done(self) -> None:
        elapsed_ms = int((self._clock() - self._started) * 1000)
        logger.info("doctor suite done name=%s elapsed_ms=%s", self.name, elapsed_ms)
