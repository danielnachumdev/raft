"""TTY color detection and ANSI painting for operator output."""

import os
import sys
from typing import Optional, TextIO

from .ansi import RESET, STYLE_CODES


class TerminalColor:
    """Whether a stream should receive ANSI color, and how to paint text."""

    @classmethod
    def want(
        cls,
        stream: Optional[TextIO] = None,
        explicit: Optional[bool] = None,
    ) -> bool:
        if explicit is not None:
            return explicit
        if os.environ.get("NO_COLOR", ""):
            return False
        if os.environ.get("FORCE_COLOR", ""):
            return True
        target = stream if stream is not None else sys.stdout
        return bool(getattr(target, "isatty", lambda: False)())

    @classmethod
    def paint(
        cls,
        text: str,
        *codes: str,
        stream: Optional[TextIO] = None,
        color: Optional[bool] = None,
    ) -> str:
        if not codes or not cls.want(stream, color):
            return text
        return f"{''.join(codes)}{text}{RESET}"

    @classmethod
    def styled(cls, message: str, style: Optional[str], stream: TextIO) -> str:
        if not message or not style:
            return message
        codes = STYLE_CODES.get(style)
        if not codes:
            return message
        return cls.paint(message, *codes, stream=stream)
