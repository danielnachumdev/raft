"""Apply-time text pipeline for App manifests (before YAML parse).

``ManifestPreprocessor`` resolves ``${{ … }}`` directives, then expands
``${VAR}``. Full-line YAML ``#`` comments are ignored (copied through).
Registry stores the concrete result — render/redeploy/doctor never re-run this.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Union

from ..env.expander import ManifestTextExpander
from .directive_resolver import DirectiveResolver


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
