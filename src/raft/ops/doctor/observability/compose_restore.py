"""Restore ``shell.compose`` after a doctor run."""

from typing import Any, Callable


class ComposeRestore:
    """Restore ``shell.compose`` after a doctor run."""

    def __init__(self, shell: Any, original: Callable[..., Any]) -> None:
        self._shell = shell
        self._original = original

    def __call__(self) -> None:
        self._shell.compose = self._original
