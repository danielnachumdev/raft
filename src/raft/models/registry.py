"""On-disk applied App registry under ``~/.raft/state/apps/``."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from raft.errors.cta import OperatorError

from .app import App
from .app_document import AppDocument
from .manifest import REGISTRY_DIR

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegistryIssue:
    """One applied manifest that failed to load (others still load)."""

    file: str
    error: str

    def to_dict(self) -> dict[str, str]:
        return {"file": self.file, "error": self.error}


@dataclass(frozen=True)
class RegistryLoadResult:
    apps: tuple[App, ...]
    issues: tuple[RegistryIssue, ...]


class AppRegistry:
    """Load, write, and delete applied App manifests for a data home."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def directory(self) -> Path:
        return self.root / REGISTRY_DIR

    def path_for(self, name: str) -> Path:
        return self.directory() / f"{name}.yaml"

    def load(self) -> tuple[App, ...]:
        return self.load_result().apps

    def load_result(self) -> RegistryLoadResult:
        directory = self.directory()
        if not directory.is_dir():
            return RegistryLoadResult((), ())
        apps: list[App] = []
        issues: list[RegistryIssue] = []
        for path in sorted(directory.glob("*.yaml")):
            app = self._try_load_named(path, issues)
            if app is not None:
                apps.append(app)
        self._assert_unique_hosts(apps)
        return RegistryLoadResult(tuple(apps), tuple(issues))

    def write(self, document: dict[str, Any]) -> Path:
        app, _ = AppDocument.parse(document, path=Path("<apply>"))
        directory = self.directory()
        directory.mkdir(parents=True, exist_ok=True)
        dest = self.path_for(app.name)
        self._assert_host_available(app, directory)
        dest.write_text(
            yaml.safe_dump(document, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        return dest

    def delete(self, name: str) -> bool:
        path = self.path_for(name)
        if not path.is_file():
            return False
        path.unlink()
        return True

    def _try_load_named(
        self, path: Path, issues: list[RegistryIssue]
    ) -> Optional[App]:
        try:
            return self._load_named(path)
        except (OperatorError, ValueError, OSError) as exc:
            issue = RegistryIssue(file=path.name, error=str(exc))
            issues.append(issue)
            logger.warning("skipping invalid registry manifest %s: %s", path.name, exc)
            return None

    @staticmethod
    def _load_named(path: Path) -> App:
        app, _ = AppDocument.load(path)
        if path.stem != app.name:
            raise ValueError(
                f"{path}: filename stem {path.stem!r} must match " f"metadata.name {app.name!r}"
            )
        return app

    @staticmethod
    def _assert_unique_hosts(apps: list[App]) -> None:
        hosts = [a.public_host.lower() for a in apps if a.public_host]
        if len(hosts) != len(set(hosts)):
            raise ValueError("registry: publicHost values must be unique across applied apps")

    @staticmethod
    def _assert_host_available(app: App, directory: Path) -> None:
        if not app.public_host:
            return
        for other in directory.glob("*.yaml"):
            if other.stem == app.name:
                continue
            other_app = AppRegistry._peek_app(other)
            if other_app is None:
                continue
            if other_app.public_host and other_app.public_host.lower() == app.public_host.lower():
                raise ValueError(
                    f"publicHost {app.public_host!r} already used by applied app "
                    f"{other_app.name!r}"
                )

    @staticmethod
    def _peek_app(path: Path) -> Optional[App]:
        try:
            return AppRegistry._load_named(path)
        except (OperatorError, ValueError, OSError):
            return None
