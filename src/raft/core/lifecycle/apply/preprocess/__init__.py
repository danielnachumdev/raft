"""Apply-time text pipeline for App manifests (before YAML parse)."""

from .preprocessor import ManifestPreprocessor
from .yaml_loader import ManifestYamlLoader

__all__ = ["ManifestPreprocessor", "ManifestYamlLoader"]
