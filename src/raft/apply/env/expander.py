"""Expand ``${…}`` in non-comment text; leave ``${{`` for directives."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Union

from ...errors.cta import OperatorError
from ..comments import ManifestFullLineComment

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class ManifestTextExpander:
    """Expand ``${…}`` in non-comment text; leave ``${{`` for directives."""

    env: Mapping[str, str]
    path: Union[Path, str, None] = None

    def expand(self, text: str) -> str:
        out: list[str] = []
        i = 0
        while i < len(text):
            i = self._expand_step(text, i, out)
        return "".join(out)

    def _expand_step(self, text: str, i: int, out: list[str]) -> int:
        comment_end = ManifestFullLineComment.end_after(text, i)
        if comment_end is not None:
            out.append(text[i:comment_end])
            return comment_end
        if text.startswith("${{", i):
            out.append("${{")
            return i + 3
        if text.startswith("${", i):
            value, end = self._expand_placeholder(text, i)
            out.append(value)
            return end
        out.append(text[i])
        return i + 1

    def _expand_placeholder(self, text: str, start: int) -> tuple[str, int]:
        """Parse and resolve one ``${…}`` starting at ``start``; return ``(value, end)``."""
        name, cursor = self._parse_placeholder_name(text, start)
        if cursor < len(text) and text[cursor] == "}":
            return self._required(name), cursor + 1
        if text.startswith(":-", cursor):
            default, end = self._parse_default_body(text, start, cursor + 2)
            return self._with_default(name, default), end
        raise self._invalid_placeholder(text[start:])

    def _parse_placeholder_name(self, text: str, start: int) -> tuple[str, int]:
        """Return ``(name, cursor_after_name)``; ``start`` points at ``${``."""
        name_match = _NAME.match(text, start + 2)
        if name_match is None:
            raise self._invalid_placeholder(text[start:])
        return name_match.group(0), name_match.end()

    def _parse_default_body(
        self,
        text: str,
        start: int,
        default_start: int,
    ) -> tuple[str, int]:
        """Return ``(default, end_after_closing_brace)`` for ``${NAME:-default}``."""
        close = text.find("}", default_start)
        if close < 0:
            raise self._invalid_placeholder(text[start:])
        return text[default_start:close], close + 1

    def _required(self, name: str) -> str:
        value = self._lookup(name)
        if value is None:
            raise self._undefined(name)
        return value

    def _with_default(self, name: str, default: str) -> str:
        value = self._lookup(name)
        return default if value is None else value

    def _lookup(self, name: str) -> Optional[str]:
        """Return the env value, or ``None`` when unset or empty (shell-style)."""
        value = self.env.get(name)
        if value is None or value == "":
            return None
        return value

    def _source_label(self) -> str:
        if self.path is None or self.path == "":
            return "manifest"
        return f"manifest at {self.path}"

    @staticmethod
    def _snippet(near: str, *, limit: int = 40) -> str:
        if len(near) <= limit:
            return near
        return near[: limit - 3] + "..."

    def _undefined(self, name: str) -> OperatorError:
        return OperatorError(
            f"{self._source_label()}: undefined variable {name} in ${{{name}}}\n"
            f"Fix: export {name}=… or pass --env-file / --env {name}=…"
        )

    def _invalid_placeholder(self, near: str) -> OperatorError:
        return OperatorError(
            f"{self._source_label()}: invalid placeholder near "
            f"{self._snippet(near)!r}\n"
            f"Fix: use ${{NAME}} or ${{NAME:-default}}"
        )
