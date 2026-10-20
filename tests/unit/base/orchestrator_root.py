"""Ensure a temporary raft data-home tree for unit tests."""

from pathlib import Path
from typing import Any, Mapping, Union

import yaml

DEFAULT_SETTINGS_YAML = (
    "logging:\n  level: INFO\n" "edge:\n  http: 80\n  https: 443\n"
)


class OrchestratorRoot:
    @classmethod
    def ensure_orchestrator_root(cls, root: Path) -> None:
        settings = root / "host" / "settings.yaml"
        if not settings.is_file():
            cls.write_settings(root, DEFAULT_SETTINGS_YAML)
        for name in (
            "services",
            "generated",
            "host",
            "host/locks",
            "host/metrics",
            "host/logs",
            "host/acme/http-01",
        ):
            (root / name).mkdir(parents=True, exist_ok=True)

    @classmethod
    def write_settings(
        cls,
        root: Path,
        body: Union[str, Mapping[str, Any]],
    ) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        path = root / "host" / "settings.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(body, Mapping):
            text = yaml.safe_dump(dict(body), sort_keys=False)
        else:
            text = body
        path.write_text(text, encoding="utf-8")
        return path

    @classmethod
    def ensure_app_checkouts(cls, root: Path, *names: str) -> None:
        for name in names:
            (root / "services" / name / "checkout").mkdir(parents=True, exist_ok=True)
