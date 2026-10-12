"""Count ``Shell.compose`` invocations for one doctor run."""

import logging
from typing import Any, Callable

from .compose_restore import ComposeRestore

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
        self._restores.append(ComposeRestore(shell, original))

    def _note(self, *args: str) -> None:
        self.total += 1
        if args and args[0] == "ps":
            self.ps += 1
