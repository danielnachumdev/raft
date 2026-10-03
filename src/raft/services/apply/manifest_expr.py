"""Boolean expressions for apply-time ``${{ if … }}`` directives.

Operands are only:

- quoted strings (``'…'`` / ``"…"``) — literal text
- ``${NAME}`` / ``${NAME:-default}`` — apply-env values (same rules as
  manifest placeholder expansion; any string shape)

Operators: ``==`` ``!=`` ``&&`` ``||``, with parentheses. No barewords.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Mapping, Optional, Sequence, Tuple, Union

from raft.errors import OperatorError

from .manifest_env import ManifestTextExpander

_STRING = re.compile(r"""(?:'([^']*)'|"([^"]*)")""")
_ENV_REF = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}"
)
Token = Tuple[str, str]
Primary = Union[str, bool]


@dataclass(frozen=True)
class DirectiveExpression:
    """Parse and evaluate a directive predicate against the apply env map."""

    env: Mapping[str, str]
    path: Union[Path, str, None] = None

    def evaluate(self, expr: str) -> bool:
        tokens = ExpressionLexer(expr, self.path).tokenize()
        return ExpressionParser(tokens, self.env, self.path).parse()


@dataclass
class ExpressionLexer:
    """Tokenize strings, ``${…}`` refs, and ``==`` ``!=`` ``&&`` ``||``."""

    text: str
    path: Union[Path, str, None] = None
    _i: int = 0

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        while True:
            self._skip_ws()
            if self._i >= len(self.text):
                return tokens
            tokens.append(self._next_token())

    def _skip_ws(self) -> None:
        while self._i < len(self.text) and self.text[self._i].isspace():
            self._i += 1

    def _next_token(self) -> Token:
        for kind, literal in (
            ("OR", "||"),
            ("AND", "&&"),
            ("EQ", "=="),
            ("NE", "!="),
        ):
            if self.text.startswith(literal, self._i):
                self._i += len(literal)
                return kind, literal
        ch = self.text[self._i]
        if ch in "()":
            self._i += 1
            return ("LPAREN" if ch == "(" else "RPAREN"), ch
        string = self._try_string()
        if string is not None:
            return "STRING", string
        env_ref = self._try_env_ref()
        if env_ref is not None:
            return "ENV", env_ref
        raise _expr_error(self.path, self.text[self._i :])

    def _try_string(self) -> Optional[str]:
        match = _STRING.match(self.text, self._i)
        if match is None:
            return None
        self._i = match.end()
        return match.group(1) if match.group(1) is not None else match.group(2)

    def _try_env_ref(self) -> Optional[str]:
        """Return the full ``${…}`` lexeme for later expand."""
        match = _ENV_REF.match(self.text, self._i)
        if match is None:
            return None
        self._i = match.end()
        return match.group(0)


@dataclass
class ExpressionParser:
    """Recursive-descent parser for directive boolean expressions."""

    tokens: Sequence[Token]
    env: Mapping[str, str]
    path: Union[Path, str, None] = None
    _pos: int = 0

    def parse(self) -> bool:
        if not self.tokens:
            raise _expr_error(self.path, "")
        value = self._parse_or()
        if not self._done():
            raise _expr_error(self.path, self.tokens[self._pos][1])
        return value

    def _parse_or(self) -> bool:
        value = self._parse_and()
        while self._match("OR"):
            right = self._parse_and()
            value = value or right
        return value

    def _parse_and(self) -> bool:
        value = self._parse_cmp()
        while self._match("AND"):
            right = self._parse_cmp()
            value = value and right
        return value

    def _parse_cmp(self) -> bool:
        left = self._parse_primary()
        if isinstance(left, bool):
            return left
        if self._match("EQ"):
            return left == self._require_str(self._parse_primary())
        if self._match("NE"):
            return left != self._require_str(self._parse_primary())
        raise _expr_error(self.path, left)

    def _parse_primary(self) -> Primary:
        if self._match("LPAREN"):
            value = self._parse_or()
            if not self._match("RPAREN"):
                raise _expr_error(self.path, "unbalanced '('")
            return value
        kind, raw = self._take()
        if kind == "STRING":
            return raw
        if kind == "ENV":
            return self._resolve_env(raw)
        raise _expr_error(self.path, raw)

    def _resolve_env(self, lexeme: str) -> str:
        """Expand one ``${…}`` with the same rules as manifest placeholders."""
        return ManifestTextExpander(self.env, path=self.path).expand(lexeme)

    def _require_str(self, value: Primary) -> str:
        if isinstance(value, bool):
            raise _expr_error(self.path, str(value).lower())
        return value

    def _match(self, kind: str) -> bool:
        if self._done() or self.tokens[self._pos][0] != kind:
            return False
        self._pos += 1
        return True

    def _take(self) -> Token:
        if self._done():
            raise _expr_error(self.path, "")
        token = self.tokens[self._pos]
        self._pos += 1
        return token

    def _done(self) -> bool:
        return self._pos >= len(self.tokens)


def _expr_error(path: Union[Path, str, None], near: str) -> OperatorError:
    label = "manifest" if path is None or path == "" else f"manifest at {path}"
    snippet = near if len(near) <= 48 else near[:45] + "..."
    return OperatorError(
        f"{label}: invalid directive expression near {snippet!r}\n"
        f"Fix: operands are 'string' / \"string\" or ${{NAME}} "
        f"(or ${{NAME:-default}}); combine with == != && ||"
    )

