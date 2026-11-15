"""Decide whether a ``docker logs --tail`` slice reaches back to a cursor."""

import re
from typing import Optional

_RFC3339 = re.compile(
    r"^(?P<base>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(?P<frac>\d+))?Z$"
)


class LogsTailCoverage:
    """Compare Docker RFC3339Nano stamps (trailing zeros trimmed) safely."""

    @staticmethod
    def reaches(text: str, cursor: str) -> bool:
        """True when the oldest timestamped line in ``text`` is ``<= cursor``.

        Then every line newer than ``cursor`` is inside ``text``, so the
        expensive full-file ``docker logs --since`` scan can be skipped.
        """
        want = LogsTailCoverage.sortable(cursor)
        first = LogsTailCoverage._first_line(text)
        if want is None or first is None:
            return False
        have = LogsTailCoverage.sortable(first.split(" ", 1)[0])
        return have is not None and have <= want

    @staticmethod
    def sortable(stamp: str) -> Optional[str]:
        match = _RFC3339.match(stamp.strip())
        if match is None:
            return None
        frac = (match.group("frac") or "")[:9].ljust(9, "0")
        return f"{match.group('base')}.{frac}Z"

    @staticmethod
    def _first_line(text: str) -> Optional[str]:
        for line in text.splitlines():
            if line.strip():
                return line.strip()
        return None
