"""Operator-facing stdout/stderr lines (plain text mirrored to the raft logger)."""

import logging
import sys
from typing import Optional

from .color import TerminalColor

_log = logging.getLogger("raft")


class OperatorSay:
    """Print to the terminal and mirror non-empty lines into structured logs."""

    @classmethod
    def say(cls, message: str = "", *, style: Optional[str] = None) -> None:
        print(TerminalColor.styled(message, style, sys.stdout), flush=True)
        if message:
            _log.info("%s", message)

    @classmethod
    def say_err(cls, message: str, *, style: str = "error") -> None:
        print(
            TerminalColor.styled(message, style, sys.stderr),
            file=sys.stderr,
            flush=True,
        )
        if message:
            _log.error("%s", message)
