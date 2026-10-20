"""On-disk applied App registry under ``~/.raft/services/<name>/app.yaml``."""

import logging
from pathlib import Path
from typing import Any, Optional

import yaml

from raft.core.core.config.paths.constants import APP_MANIFEST_FILENAME
from raft.core.core.config.paths.service_paths import ServicePaths
from raft.core.core.errors.cta import OperatorError
from .app import App
from .app_document import AppDocument
from .manifest import REGISTRY_DIR
from .registry_issue import RegistryIssue, RegistryLoadResult
from .source_identity import AppSourceIdentity

logger = logging.getLogger(__name__)


class AppRegistry:
    """Load, write, and delete applied App manifests for a data home."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def directory(self) -> Path:
        return self.root / REGISTRY_DIR

    def path_for(self, name: str) -> Path:
        return ServicePaths(self.root, name).app_yaml()

    def load(self) -> tuple[App, ...]:
        return self.load_result().apps

    def load_result(self) -> RegistryLoadResult:
        directory = self.directory()
        if not directory.is_dir():
            return RegistryLoadResult((), ())
        apps: list[App] = []
        issues: list[RegistryIssue] = []
        for path in sorted(self._iter_manifests(directory)):
            app = self._try_load_named(path, issues)
            if app is not None:
                apps.append(app)
        self._assert_unique_hosts(apps)
        return RegistryLoadResult(tuple(apps), tuple(issues))

    def write(self, document: dict[str, Any]) -> Path:
        app, app_spec = AppDocument.parse(document, path=Path("<apply>"))
        dest = self.path_for(app.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        ServicePaths(self.root, app.name).ensure_scaffold()
        self._assert_source_owned(app, dest)
        self._assert_host_available(app)
        payload = self._canonical_for_dump(document, tls=app_spec.tls)
        dest.write_text(
            yaml.safe_dump(payload, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        return dest

    @staticmethod
    def _canonical_for_dump(document: dict[str, Any], *, tls: str) -> dict[str, Any]:
        """Emit parsed ``spec.tls`` so YAML 1.1 ``off`` is never dumped as bool."""
        payload = dict(document)
        spec = payload.get("spec")
        base = dict(spec) if isinstance(spec, dict) else {}
        payload["spec"] = {**base, "tls": tls}
        return payload

    def delete(self, name: str) -> bool:
        path = self.path_for(name)
        if not path.is_file():
            return False
        path.unlink()
        return True

    @staticmethod
    def _iter_manifests(directory: Path) -> list[Path]:
        found: list[Path] = []
        for child in sorted(directory.iterdir()):
            if not child.is_dir():
                continue
            manifest = child / APP_MANIFEST_FILENAME
            if manifest.is_file():
                found.append(manifest)
        return found

    def _try_load_named(
        self, path: Path, issues: list[RegistryIssue]
    ) -> Optional[App]:
        try:
            return self._load_named(path)
        except (OperatorError, ValueError, OSError) as exc:
            issue = RegistryIssue(file=path.parent.name, error=str(exc))
            issues.append(issue)
            logger.warning(
                "skipping invalid registry manifest %s: %s", path.parent.name, exc
            )
            return None

    @staticmethod
    def _load_named(path: Path) -> App:
        app, _ = AppDocument.load(path)
        if path.parent.name != app.name:
            raise ValueError(
                f"{path}: service directory {path.parent.name!r} must match "
                f"metadata.name {app.name!r}"
            )
        return app

    @staticmethod
    def _assert_source_owned(app: App, dest: Path) -> None:
        if not dest.is_file():
            return
        existing = AppRegistry._peek_app(dest)
        if existing is None:
            return
        AppSourceIdentity.reject_takeover(existing, app)

    @staticmethod
    def _assert_unique_hosts(apps: list[App]) -> None:
        hosts = [a.public_host.lower() for a in apps if a.public_host]
        if len(hosts) != len(set(hosts)):
            raise ValueError(
                "registry: publicHost values must be unique across applied apps"
            )

    def _assert_host_available(self, app: App) -> None:
        if not app.public_host:
            return
        for other_path in self._iter_manifests(self.directory()):
            if other_path.parent.name == app.name:
                continue
            other_app = AppRegistry._peek_app(other_path)
            if other_app is None:
                continue
            if (
                other_app.public_host
                and other_app.public_host.lower() == app.public_host.lower()
            ):
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
