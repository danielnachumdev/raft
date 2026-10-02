"""Parse human-readable ``docker stats`` size / percent fields."""

from __future__ import annotations

from typing import Optional, Sequence


class DockerStatsText:
    """Parse human-readable ``docker stats`` size / percent fields."""

    @classmethod
    def parse_size(cls, value: str) -> Optional[int]:
        """Parse docker human sizes (``1.5MiB``, ``64MB``, ``1024B``) to bytes."""
        text = (value or "").strip()
        if not text or text in ("--", "0"):
            return 0 if text == "0" else None
        parsed = cls._size_with_unit(text)
        if parsed is not None:
            return parsed
        try:
            return int(float(text))
        except ValueError:
            return None

    @staticmethod
    def _size_with_unit(text: str) -> Optional[int]:
        units: Sequence[tuple[str, int]] = (
            ("KiB", 1024),
            ("MiB", 1024**2),
            ("GiB", 1024**3),
            ("TiB", 1024**4),
            ("kB", 1000),
            ("MB", 1000**2),
            ("GB", 1000**3),
            ("TB", 1000**4),
            ("B", 1),
        )
        for suffix, factor in units:
            if text.endswith(suffix):
                number = text[: -len(suffix)].strip()
                try:
                    return int(float(number) * factor)
                except ValueError:
                    return None
        return None

    @classmethod
    def parse_pair(cls, value: str) -> tuple[Optional[int], Optional[int]]:
        """Parse ``a / b`` pairs from ``docker stats`` (MemUsage, NetIO, BlockIO)."""
        text = (value or "").strip()
        if " / " not in text:
            return (cls.parse_size(text), None)
        left, right = text.split(" / ", 1)
        return (cls.parse_size(left), cls.parse_size(right))

    @staticmethod
    def parse_percent(value: str) -> Optional[float]:
        text = (value or "").strip().rstrip("%")
        if not text or text == "--":
            return None
        try:
            return float(text)
        except ValueError:
            return None
