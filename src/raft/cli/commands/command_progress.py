"""Enter TerminalProgress for long-running commands before RaftCLI init."""

from __future__ import annotations

from typing import Optional, Sequence

from raft.ui.progress import TerminalProgress


class CommandProgress:
    """Context manager: start the doctor/update spinner before stack/logging setup.

    ``RaftCLI.__init__`` may spend seconds on log retention prune. Entering the
    spinner here means the TTY shows activity during that work. Doctor/update
    reuse ``TerminalProgress.current()`` instead of nesting a second spinner.
    """

    _SPECS = {
        "doctor": ("raft doctor", "checking"),
        "purge": ("raft purge", "purging"),
        "update": ("raft update", "updating"),
    }

    def __init__(self, command: Sequence[str]) -> None:
        key = command[0] if command else ""
        self._spec = self._SPECS.get(key)
        self._progress: Optional[TerminalProgress] = None

    def __enter__(self) -> Optional[TerminalProgress]:
        if self._spec is None:
            return None
        prefix, label = self._spec
        self._progress = TerminalProgress(prefix=prefix, label=label)
        return self._progress.__enter__()

    def __exit__(self, *exc) -> None:
        if self._progress is not None:
            self._progress.__exit__(*exc)
