"""Recursive-descent parser for directive boolean expressions."""

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence, Union

from ..env.expander import ManifestTextExpander
from .error import DirectiveExpressionError
from .tokens import Primary, Token


@dataclass
class ExpressionParser:
    """Recursive-descent parser for directive boolean expressions."""

    tokens: Sequence[Token]
    env: Mapping[str, str]
    path: Union[Path, str, None] = None
    _pos: int = 0

    def parse(self) -> bool:
        if not self.tokens:
            raise DirectiveExpressionError(self.path).near("")
        value = self._parse_or()
        if not self._done():
            raise DirectiveExpressionError(self.path).near(self.tokens[self._pos][1])
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
        raise DirectiveExpressionError(self.path).near(left)

    def _parse_primary(self) -> Primary:
        if self._match("LPAREN"):
            value = self._parse_or()
            if not self._match("RPAREN"):
                raise DirectiveExpressionError(self.path).near("unbalanced '('")
            return value
        kind, raw = self._take()
        if kind == "STRING":
            return raw
        if kind == "ENV":
            return self._resolve_env(raw)
        raise DirectiveExpressionError(self.path).near(raw)

    def _resolve_env(self, lexeme: str) -> str:
        """Expand one ``${…}`` with the same rules as manifest placeholders."""
        return ManifestTextExpander(self.env, path=self.path).expand(lexeme)

    def _require_str(self, value: Primary) -> str:
        if isinstance(value, bool):
            raise DirectiveExpressionError(self.path).near(str(value).lower())
        return value

    def _match(self, kind: str) -> bool:
        if self._done() or self.tokens[self._pos][0] != kind:
            return False
        self._pos += 1
        return True

    def _take(self) -> Token:
        if self._done():
            raise DirectiveExpressionError(self.path).near("")
        token = self.tokens[self._pos]
        self._pos += 1
        return token

    def _done(self) -> bool:
        return self._pos >= len(self.tokens)
