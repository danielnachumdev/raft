"""Helpers for loading generated compose/nginx artifacts.

Prefer ``tests.shared.artifacts.GeneratedArtifacts`` for new code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.shared.artifacts import GeneratedArtifacts


def load_compose_apps(generated: Path) -> dict[str, Any]:
    return GeneratedArtifacts(generated).compose_apps()


def load_compose_edge(generated: Path) -> dict[str, Any]:
    return GeneratedArtifacts(generated).compose_edge()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")
