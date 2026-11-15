"""Apply App manifests into the operator registry."""

from .comments import ManifestFullLineComment
from .env import (
    ApplyEnvSources,
    DotenvLoader,
    EnvAssignment,
    ManifestTextExpander,
)
from .expr import DirectiveExpression
from .preprocess import ManifestPreprocessor, ManifestYamlLoader
from .delete import AppDelete
from .service import AppApply

__all__ = [
    "AppApply",
    "AppDelete",
    "ApplyEnvSources",
    "DirectiveExpression",
    "DotenvLoader",
    "EnvAssignment",
    "ManifestFullLineComment",
    "ManifestPreprocessor",
    "ManifestTextExpander",
    "ManifestYamlLoader",
]
