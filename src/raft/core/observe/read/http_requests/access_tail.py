"""Read recent lines from the gate HTTP access log."""

from pathlib import Path
from typing import List

DEFAULT_MAX_READ_BYTES = 512_000


class AccessLogTail:
    """Return trailing text lines from ``access.log`` (newest last)."""

    def __init__(
        self,
        path: Path,
        *,
        max_read_bytes: int = DEFAULT_MAX_READ_BYTES,
    ) -> None:
        self.path = path
        self.max_read_bytes = max_read_bytes

    def lines(self) -> List[str]:
        if not self.path.is_file():
            return []
        try:
            raw = self._read_tail_bytes()
        except OSError:
            return []
        text = raw.decode("utf-8", errors="replace")
        return [line for line in text.splitlines() if line.strip()]

    def _read_tail_bytes(self) -> bytes:
        size = self.path.stat().st_size
        if size <= 0:
            return b""
        start = max(0, size - self.max_read_bytes)
        with self.path.open("rb") as handle:
            handle.seek(start)
            data = handle.read()
        if start > 0:
            nl = data.find(b"\n")
            if nl >= 0:
                data = data[nl + 1 :]
        return data
