"""Enter TerminalProgress for long-running commands before RaftCLICommands init."""

from typing import Optional, Sequence

from raft.core.core.ui.progress import TerminalProgress


class CommandProgress:
    """Context manager: start a spinner before stack/logging setup.

    ``RaftCLICommands.__init__`` may spend seconds on log retention prune.
    Entering the spinner here means the TTY shows activity during that work.
    Long verbs reuse ``TerminalProgress.current()`` instead of nesting a second
    spinner. Instant verbs (status/get/logs/…) stay quiet on purpose.
    """

    _SPECS = {
        "doctor": ("raft doctor", "checking"),
        "purge": ("raft purge", "purging"),
        "update": ("raft update", "updating"),
        "apply": ("raft apply", "applying"),
        "delete": ("raft delete", "deleting"),
        "up": ("raft up", "starting"),
        "down": ("raft down", "stopping"),
        "render": ("raft render", "rendering"),
        "sync": ("raft sync", "syncing"),
        "redeploy": ("raft redeploy", "redeploying"),
        "uninstall": ("raft uninstall", "uninstalling"),
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
