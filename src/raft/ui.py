"""Operator-facing terminal output (plain prints). Logs stay in the log file."""

import logging
import sys

_log = logging.getLogger("raft")


def say(message: str = "") -> None:
    print(message, flush=True)
    if message:
        _log.info("%s", message)


def say_err(message: str) -> None:
    print(message, file=sys.stderr, flush=True)
    _log.error("%s", message)
