"""Path read + substring asserts for generated files."""

from __future__ import annotations

from pathlib import Path


class FileText:
    """Read UTF-8 file text and assert expected substrings."""

    @staticmethod
    def read(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    @classmethod
    def contains(cls, path: Path, *needles: str) -> str:
        text = cls.read(path)
        for needle in needles:
            assert needle in text, f"missing {needle!r} in {path}: {text!r}"
        return text
