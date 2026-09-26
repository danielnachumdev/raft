"""Load generated compose/nginx artifacts for assert-friendly tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class GeneratedArtifacts:
    """Read ``generated/`` compose YAML and nested nginx paths."""

    def __init__(self, generated: Path) -> None:
        self.generated = generated

    @classmethod
    def under(cls, home: Path) -> "GeneratedArtifacts":
        return cls(home / "generated")

    def path(self, *parts: str) -> Path:
        return self.generated.joinpath(*parts)

    def text(self, *parts: str) -> str:
        return self.path(*parts).read_text(encoding="utf-8")

    def compose_apps(self) -> dict[str, Any]:
        return self._load_yaml("compose.apps.yaml")

    def compose_edge(self) -> dict[str, Any]:
        return self._load_yaml("compose.edge.yaml")

    def compose_apps_text(self) -> str:
        return self.text("compose.apps.yaml")

    def compose_edge_text(self) -> str:
        return self.text("compose.edge.yaml")

    def _load_yaml(self, name: str) -> dict[str, Any]:
        data = yaml.safe_load(self.text(name))
        assert isinstance(data, dict)
        return data
