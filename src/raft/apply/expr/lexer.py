"""Tokenize directive expression operands and operators."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

from .error import DirectiveExpressionError
from .tokens import Token

_STRING = re.compile(r"""(?:'([^']*)'|"([^"]*)")""")
_ENV_REF = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}"
)


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
        raise DirectiveExpressionError(self.path).near(self.text[self._i :])

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
