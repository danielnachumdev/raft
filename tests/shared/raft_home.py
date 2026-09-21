"""Cross-tier helpers: fixture paths, apply + render into a temp raft home."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

import yaml

from raft.config.paths import ensure_raft_home
from raft.config.settings import EdgeConfig, EdgeStream
from raft.models.stack import load_stack
from raft.services.apply import AppApply
from raft.services.render import StackRenderer

# tests/fixtures
FIXTURES_ROOT = Path(__file__).resolve().parent.parent / "fixtures"


def fixture_dir(name: str) -> Path:
    path = FIXTURES_ROOT / name
    if not path.is_dir():
        raise FileNotFoundError(f"missing fixture tree: {path}")
    return path


def fixture_app_yamls(name: str) -> list[Path]:
    """Return all ``*/.raft/app.yaml`` (or top-level ``app.yaml``) under a fixture."""
    return fixture_app_yamls_under(fixture_dir(name))


def prepare_raft_home(home: Path, *, settings: Optional[dict] = None) -> Path:
    ensure_raft_home(home)
    if settings is not None:
        (home / "settings.yaml").write_text(
            yaml.safe_dump(settings, sort_keys=False),
            encoding="utf-8",
        )
    elif not (home / "settings.yaml").is_file():
        (home / "settings.yaml").write_text(
            "logging:\n  level: INFO\n"
            "edge:\n  http: 80\n  https: 443\n  streams: []\n",
            encoding="utf-8",
        )
    return home


def apply_and_render(
    home: Path,
    app_yaml_paths: Sequence[Path],
    *,
    edge: Optional[EdgeConfig] = None,
) -> Path:
    """Apply manifests into ``home`` and run ``StackRenderer.render``.

    Returns the generated/ directory.
    """
    prepare_raft_home(home)
    stack = load_stack(home)
    apply = AppApply(stack)
    for path in app_yaml_paths:
        apply.apply_file(path, deploy=False)
        # Refresh stack after each apply so dependsOn sees prior apps.
        stack = load_stack(home)
        apply = AppApply(stack)
    stack = load_stack(home)
    for app in stack.apps:
        (home / "apps" / app.name).mkdir(parents=True, exist_ok=True)
    kwargs = {}
    if edge is not None:
        kwargs["edge"] = edge
    StackRenderer(stack, **kwargs).render()
    return home / "generated"


def edge_with_smtp_stream() -> EdgeConfig:
    return EdgeConfig(
        http=80,
        https=443,
        streams=(EdgeStream(name="smtp", port=25, protocol="tcp"),),
    )


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
