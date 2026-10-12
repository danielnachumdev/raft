"""Preprocess raw manifest text, then ``yaml.safe_load``."""

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Union

import yaml

from .preprocessor import ManifestPreprocessor


@dataclass(frozen=True)
class ManifestYamlLoader:
    """Preprocess raw manifest text, then ``yaml.safe_load``."""

    env: Mapping[str, str]

    def load(self, raw: str, *, path: Union[Path, str]):
        text = ManifestPreprocessor(self.env, path=path).preprocess(raw)
        return yaml.safe_load(text)
