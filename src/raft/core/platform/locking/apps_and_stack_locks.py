"""Acquire app locks in sorted order, then the stack lock."""

from contextlib import ExitStack
from pathlib import Path
from typing import Optional, Sequence

from .app_deploy_lock import AppDeployLock
from .stack_lock import StackLock


class AppsAndStackLocks:
    """Acquire app locks in sorted name order, then stack (avoids deadlock)."""

    def __init__(
        self,
        root: Path,
        names: Sequence[str],
        *,
        timeout: Optional[float] = None,
    ) -> None:
        self._root = root
        self._names = sorted({n for n in names if n})
        self._timeout = timeout
        self._stack: Optional[ExitStack] = None

    def __enter__(self) -> None:
        stack = ExitStack()
        stack.__enter__()
        try:
            self._enter_all(stack)
        except BaseException:
            stack.__exit__(None, None, None)
            raise
        self._stack = stack

    def __exit__(self, *exc) -> None:
        if self._stack is None:
            return
        self._stack.__exit__(*exc)
        self._stack = None

    def _enter_all(self, stack: ExitStack) -> None:
        for name in self._names:
            stack.enter_context(
                AppDeployLock(self._root, name, timeout=self._timeout)
            )
        stack.enter_context(StackLock(self._root, timeout=self._timeout))
