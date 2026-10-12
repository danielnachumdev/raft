"""Operator errors for invalid directive boolean expressions."""

from dataclasses import dataclass
from pathlib import Path
from typing import Union

from ...errors.cta import OperatorError


@dataclass(frozen=True)
class DirectiveExpressionError:
    """Build ``OperatorError`` for an invalid ``${{ if … }}`` predicate."""

    path: Union[Path, str, None] = None

    def near(self, near: str) -> OperatorError:
        label = self._source_label()
        snippet = near if len(near) <= 48 else near[:45] + "..."
        return OperatorError(
            f"{label}: invalid directive expression near {snippet!r}\n"
            f"Fix: operands are 'string' / \"string\" or ${{NAME}} "
            f"(or ${{NAME:-default}}); combine with == != && ||"
        )

    def _source_label(self) -> str:
        if self.path is None or self.path == "":
            return "manifest"
        return f"manifest at {self.path}"
