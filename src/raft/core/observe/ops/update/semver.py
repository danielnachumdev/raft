"""Normalize and compare release tags / package versions (no packaging dep)."""

from __future__ import annotations

from typing import Optional, Tuple


class SemverParts:
    """Parse ``v1.2.3`` / ``1.2.3rc1`` into comparable numeric tuples."""

    @classmethod
    def parse(cls, raw: str) -> Optional[Tuple[int, ...]]:
        text = (raw or "").strip()
        if text.lower().startswith("v") and len(text) > 1 and text[1].isdigit():
            text = text[1:]
        if not text or not text[0].isdigit():
            return None
        parts: list[int] = []
        for chunk in text.split("."):
            num = cls._leading_int(chunk)
            if num is None:
                break
            parts.append(num)
        return tuple(parts) if parts else None

    @staticmethod
    def _leading_int(chunk: str) -> Optional[int]:
        digits = []
        for ch in chunk:
            if ch.isdigit():
                digits.append(ch)
            else:
                break
        if not digits:
            return None
        return int("".join(digits))

    @classmethod
    def compare(cls, left: str, right: str) -> Optional[int]:
        """Return -1 / 0 / 1, or ``None`` when either side is unparsable."""
        a = cls.parse(left)
        b = cls.parse(right)
        if a is None or b is None:
            return None
        # Pad so (1, 2) vs (1, 2, 0) compare equal at shared length.
        width = max(len(a), len(b))
        aa = a + (0,) * (width - len(a))
        bb = b + (0,) * (width - len(b))
        if aa < bb:
            return -1
        if aa > bb:
            return 1
        return 0
