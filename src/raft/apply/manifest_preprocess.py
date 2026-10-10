"""Apply-time text pipeline for App manifests (before YAML parse).

``ManifestPreprocessor`` resolves ``${{ … }}`` directives, then expands
``${VAR}``. Full-line YAML ``#`` comments are ignored (copied through).
Registry stores the concrete result — render/redeploy/doctor never re-run this.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Union

import yaml

from raft.errors.cta import OperatorError

from .manifest_comments import ManifestFullLineComment
from .manifest_env import ManifestTextExpander
from .manifest_expr import DirectiveExpression

_ENDIF = re.compile(r"^endif\b(.*)$", flags=re.DOTALL)
_IF = re.compile(r"^if\b(.*)$", flags=re.DOTALL)


@dataclass(frozen=True)
class ManifestPreprocessor:
    """High-level apply-time transforms over raw manifest text.

    Callers should depend on ``preprocess``. New abilities become additional
    declarative steps on this class (or collaborators it owns).
    """

    env: Mapping[str, str]
    path: Union[Path, str, None] = None

    def preprocess(self, text: str) -> str:
        """Run the full text pipeline (order is part of the contract).

        Directives first so ``${{ if ${NAME} == 'x' }}`` keeps env refs intact
        for the expression parser; then expand remaining ``${VAR}`` in the body.
        """
        text = self.resolve_directives(text)
        text = self.expand_variables(text)
        return text

    def expand_variables(self, text: str) -> str:
        """Substitute ``${NAME}`` / ``${NAME:-default}`` from the apply env map."""
        return ManifestTextExpander(self.env, path=self.path).expand(text)

    def resolve_directives(self, text: str) -> str:
        """Resolve ``${{ … }}`` blocks (``if`` / ``endif``, nesting allowed)."""
        return DirectiveResolver(self.env, self.path).resolve(text)


@dataclass(frozen=True)
class ManifestYamlLoader:
    """Preprocess raw manifest text, then ``yaml.safe_load``."""

    env: Mapping[str, str]

    def load(self, raw: str, *, path: Union[Path, str]):
        text = ManifestPreprocessor(self.env, path=path).preprocess(raw)
        return yaml.safe_load(text)


@dataclass
class DirectiveResolver:
    """Single-pass ``${{ }}`` resolver with a nestable ``if`` / ``endif`` stack."""

    env: Mapping[str, str]
    path: Union[Path, str, None] = None
    _frames: list[bool] = field(default_factory=list)
    _out: list[str] = field(default_factory=list)

    def resolve(self, text: str) -> str:
        i = 0
        while i < len(text):
            i = self._step(text, i)
        self._reject_unclosed()
        return "".join(self._out)

    def _emitting(self) -> bool:
        return all(self._frames) if self._frames else True

    def _step(self, text: str, i: int) -> int:
        comment_end = ManifestFullLineComment.end_after(text, i)
        if comment_end is not None:
            return self._copy_span(text, i, comment_end)
        if text.startswith("${{", i):
            return self._handle_directive(text, i)
        if self._emitting():
            self._out.append(text[i])
        return i + 1

    def _copy_span(self, text: str, start: int, end: int) -> int:
        if self._emitting():
            self._out.append(text[start:end])
        return end

    def _handle_directive(self, text: str, start: int) -> int:
        body, end = self._read_directive_body(text, start)
        kind, rest = self._split_directive(body, text[start:])
        if kind == "if":
            self._enter_if(rest)
        else:
            self._leave_endif(rest, text[start:])
        return self._finish_sole_directive_line(text, start, end)

    def _read_directive_body(self, text: str, start: int) -> tuple[str, int]:
        close = text.find("}}", start + 3)
        if close < 0:
            raise self._unclosed_directive(text[start:])
        return text[start + 3 : close].strip(), close + 2

    def _finish_sole_directive_line(self, text: str, start: int, end: int) -> int:
        """Drop a directive-only line (indent + newline) from the output stream."""
        line_start = text.rfind("\n", 0, start) + 1
        prefix = text[line_start:start]
        if prefix.strip():
            return end
        j = end
        while j < len(text) and text[j] in " \t":
            j += 1
        if j < len(text) and text[j] == "\n":
            self._trim_emitted_prefix(prefix)
            return j + 1
        if j == len(text):
            self._trim_emitted_prefix(prefix)
            return j
        return end

    def _trim_emitted_prefix(self, prefix: str) -> None:
        n = len(prefix)
        if n and n <= len(self._out) and "".join(self._out[-n:]) == prefix:
            del self._out[-n:]

    def _split_directive(self, body: str, near: str) -> tuple[str, str]:
        endif = _ENDIF.match(body)
        if endif is not None:
            return "endif", endif.group(1).strip()
        if_dir = _IF.match(body)
        if if_dir is not None:
            return "if", if_dir.group(1).strip()
        raise self._unknown_directive(body, near)

    def _enter_if(self, expr: str) -> None:
        parent_ok = self._emitting()
        cond = DirectiveExpression(self.env, self.path).evaluate(expr)
        self._frames.append(parent_ok and cond)

    def _leave_endif(self, rest: str, near: str) -> None:
        if rest:
            raise self._unknown_directive(f"endif {rest}".strip(), near)
        if not self._frames:
            raise self._unmatched_endif(near)
        self._frames.pop()

    def _reject_unclosed(self) -> None:
        if self._frames:
            raise self._unclosed_if()

    def _source_label(self) -> str:
        if self.path is None or self.path == "":
            return "manifest"
        return f"manifest at {self.path}"

    @staticmethod
    def _snippet(near: str, *, limit: int = 48) -> str:
        if len(near) <= limit:
            return near
        return near[: limit - 3] + "..."

    def _unmatched_endif(self, near: str) -> OperatorError:
        return OperatorError(
            f"{self._source_label()}: ${{{{ endif }}}} without matching "
            f"${{{{ if }}}} near {self._snippet(near)!r}\n"
            f"Fix: add ${{{{ if expr }}}} before ${{{{ endif }}}}"
        )

    def _unclosed_if(self) -> OperatorError:
        return OperatorError(
            f"{self._source_label()}: ${{{{ if }}}} without matching "
            f"${{{{ endif }}}}\n"
            f"Fix: close every ${{{{ if }}}} with ${{{{ endif }}}}"
        )

    def _unclosed_directive(self, near: str) -> OperatorError:
        return OperatorError(
            f"{self._source_label()}: unclosed ${{{{ near "
            f"{self._snippet(near)!r}\n"
            f"Fix: close directives as ${{{{ if expr }}}} / ${{{{ endif }}}}"
        )

    def _unknown_directive(self, body: str, near: str) -> OperatorError:
        return OperatorError(
            f"{self._source_label()}: unknown directive ${{{{{body}}}}} near "
            f"{self._snippet(near)!r}\n"
            f"Fix: use ${{{{ if expr }}}} or ${{{{ endif }}}} "
            f"(expr: == != && ||)"
        )
