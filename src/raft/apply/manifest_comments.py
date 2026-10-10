"""Full-line YAML ``#`` comments are ignored by apply-time preprocess."""

from __future__ import annotations

from typing import Optional


class ManifestFullLineComment:
    """Detect and skip lines that are only whitespace + ``#`` … newline."""

    @staticmethod
    def at_line_start(text: str, index: int) -> bool:
        return index == 0 or text[index - 1] == "\n"

    @classmethod
    def end_after(cls, text: str, index: int) -> Optional[int]:
        """Return index after a full-line comment starting at ``index``, or None."""
        if not cls.at_line_start(text, index):
            return None
        cursor = index
        while cursor < len(text) and text[cursor] in " \t":
            cursor += 1
        if cursor >= len(text) or text[cursor] != "#":
            return None
        newline = text.find("\n", index)
        if newline < 0:
            return len(text)
        return newline + 1
