"""Boolean expressions for apply-time ``${{ if … }}`` directives.

Operands are only:

- quoted strings (``'…'`` / ``"…"``) — literal text
- ``${NAME}`` / ``${NAME:-default}`` — apply-env values (same rules as
  manifest placeholder expansion; any string shape)

Operators: ``==`` ``!=`` ``&&`` ``||``, with parentheses. No barewords.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Union

from .lexer import ExpressionLexer
from .parser import ExpressionParser


@dataclass(frozen=True)
class DirectiveExpression:
    """Parse and evaluate a directive predicate against the apply env map."""

    env: Mapping[str, str]
    path: Union[Path, str, None] = None

    def evaluate(self, expr: str) -> bool:
        tokens = ExpressionLexer(expr, self.path).tokenize()
        return ExpressionParser(tokens, self.env, self.path).parse()
