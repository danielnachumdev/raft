"""Operator-facing terminal output. Logs stay plain in the log file."""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional, TextIO

_log = logging.getLogger("raft")

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"

_STYLE_CODES = {
    "ok": (GREEN,),
    "warn": (YELLOW,),
    "error": (RED, BOLD),
    "info": (CYAN,),
}


def want_color(stream: Optional[TextIO] = None, explicit: Optional[bool] = None) -> bool:
    if explicit is not None:
        return explicit
    if os.environ.get("NO_COLOR", ""):
        return False
    if os.environ.get("FORCE_COLOR", ""):
        return True
    target = stream if stream is not None else sys.stdout
    return bool(getattr(target, "isatty", lambda: False)())


def paint(
    text: str,
    *codes: str,
    stream: Optional[TextIO] = None,
    color: Optional[bool] = None,
) -> str:
    if not codes or not want_color(stream, color):
        return text
    return f"{''.join(codes)}{text}{RESET}"


def _styled(message: str, style: Optional[str], stream: TextIO) -> str:
    if not message or not style:
        return message
    codes = _STYLE_CODES.get(style)
    if not codes:
        return message
    return paint(message, *codes, stream=stream)


def say(message: str = "", *, style: Optional[str] = None) -> None:
    print(_styled(message, style, sys.stdout), flush=True)
    if message:
        _log.info("%s", message)


def say_err(message: str, *, style: str = "error") -> None:
    print(_styled(message, style, sys.stderr), file=sys.stderr, flush=True)
    if message:
        _log.error("%s", message)
