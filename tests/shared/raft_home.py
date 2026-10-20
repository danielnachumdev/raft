"""Cross-tier helpers: fixture paths, apply + render into a temp raft home."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

import yaml

from raft.core.core.config.paths import RaftHomeBootstrap
from raft.core.core.config.settings.types import EdgeConfig, EdgeStream
from raft.core.core.models.stack import load_stack
from raft.core.lifecycle.apply import AppApply
from raft.core.lifecycle.render import StackRenderer

FIXTURES_ROOT = Path(__file__).resolve().parent.parent / "fixtures"


class RaftHomeFixtures:
    """Class-owned helpers for integration/e2e raft-home setup."""

    @staticmethod
    def fixture_dir(name: str) -> Path:
        path = FIXTURES_ROOT / name
        if not path.is_dir():
            raise FileNotFoundError(f"missing fixture tree: {path}")
        return path

    @classmethod
    def fixture_app_yamls(cls, name: str) -> list[Path]:
        return cls.fixture_app_yamls_under(cls.fixture_dir(name))

    @staticmethod
    def prepare(home: Path, *, settings: Optional[dict] = None) -> Path:
        RaftHomeBootstrap().ensure(home)
        settings_path = home / "host" / "settings.yaml"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        if settings is not None:
            settings_path.write_text(
                yaml.safe_dump(settings, sort_keys=False),
                encoding="utf-8",
            )
        elif not settings_path.is_file():
            settings_path.write_text(
                "logging:\n  level: INFO\n" "edge:\n  http: 80\n  https: 443\n  streams: []\n",
                encoding="utf-8",
            )
        return home

    @classmethod
    def apply_and_render(
        cls,
        home: Path,
        app_yaml_paths: Sequence[Path],
        *,
        edge: Optional[EdgeConfig] = None,
    ) -> Path:
        cls.prepare(home)
        stack = load_stack(home)
        apply = AppApply(stack)
        for path in app_yaml_paths:
            apply.apply_file(path, deploy=False)
            stack = load_stack(home)
            apply = AppApply(stack)
        stack = load_stack(home)
        for app in stack.apps:
            (home / "services" / app.name / "checkout").mkdir(parents=True, exist_ok=True)
        kwargs = {}
        if edge is not None:
            kwargs["edge"] = edge
        StackRenderer(stack, **kwargs).render()
        return home / "generated"

    @staticmethod
    def edge_with_smtp_stream() -> EdgeConfig:
        return EdgeConfig(
            http=80,
            https=443,
            streams=(EdgeStream(name="smtp", port=25, protocol="tcp"),),
        )

    @staticmethod
    def fixture_app_yamls_under(root: Path) -> list[Path]:
        found = sorted(root.glob("*/.raft/app.yaml"))
        if found:
            return found
        nested = root / ".raft" / "app.yaml"
        if nested.is_file():
            return [nested]
        single = root / "app.yaml"
        if single.is_file():
            return [single]
        raise FileNotFoundError(f"no app.yaml under {root}")
