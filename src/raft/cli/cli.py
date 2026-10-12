"""Process entry: Fire dispatch, logging bootstrap, error → exit mapping."""

import logging
import os
import sys
from typing import Optional

from ..utils import TraceContext

from .commands import RaftCLICommands
from .exit_mapper import CliExitMapper
from .utils.argv import ApplyEnvArgvBridge
from .utils.command_progress import CommandProgress
from .utils.fire_run import FireRunner
from .utils.logs_argv import LogsArgvNormalizer


class RaftCLI:
    """Process entry: logging bootstrap, trace context, Fire dispatch."""

    def __init__(self) -> None:
        self._exits = CliExitMapper()
        self._fire = FireRunner()

    def run(self, argv: Optional[list[str]] = None) -> None:
        """Bootstrap logging, open a request trace, then run one CLI invocation."""
        self._ensure_logging_bootstrap()
        with TraceContext():
            self._exits.run_guarded(self._invoke_fire, argv)

    def _invoke_fire(self, argv: Optional[list[str]] = None) -> int:
        """Normalize argv and dispatch to ``RaftCLICommands`` via Fire."""
        os.environ["PAGER"] = "cat"
        raw = list(argv) if argv is not None else sys.argv[1:]
        bridge = ApplyEnvArgvBridge()
        command, token = bridge.bind(raw)
        command = LogsArgvNormalizer().normalize(command)
        try:
            with CommandProgress(command):
                self._fire.run(RaftCLICommands, command=command, name="raft")
        finally:
            bridge.reset(token)
        return 0

    def _ensure_logging_bootstrap(self) -> None:
        root = logging.getLogger("raft")
        if root.handlers:
            return
        root.addHandler(logging.NullHandler())
        root.setLevel(logging.INFO)
        root.propagate = False
