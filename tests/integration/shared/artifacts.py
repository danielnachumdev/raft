"""Helpers for loading generated compose/nginx artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_compose_apps(generated: Path) -> dict[str, Any]:
    data = yaml.safe_load((generated / "compose.apps.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def load_compose_edge(generated: Path) -> dict[str, Any]:
    data = yaml.safe_load((generated / "compose.edge.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")
