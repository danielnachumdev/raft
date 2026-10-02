"""SSE framing for ``Logs.follow`` lines (serve live log stream)."""

from __future__ import annotations

from typing import Iterator


class LogSseStream:
    """Format follow lines as Server-Sent Events."""

    @staticmethod
    def events(lines: Iterator[str]) -> Iterator[str]:
        for line in lines:
            yield LogSseStream._event(line)

    @staticmethod
    def _event(line: str) -> str:
        # One SSE data field per log line; strip CR so framing stays intact.
        return f"data: {line.replace(chr(13), '')}\n\n"
