"""Import ``services/<name>/app.yaml`` and per-App ``deploy/`` pins into DB rows."""

from pathlib import Path
from typing import Optional

import yaml
from sqlalchemy.orm import Session

from raft.core.core.config.paths.constants import APP_MANIFEST_FILENAME
from raft.core.core.config.paths.service_paths import ServicePaths
from raft.core.core.db.models.apps import AppRow, DeployPinRow
from raft.core.core.models.app_document import AppDocument
from raft.core.core.models.manifest import (
    CONTRACT_API_VERSION,
    CONTRACT_KIND,
    REGISTRY_DIR,
)
from raft.core.core.models.source_identity import AppSourceIdentity


class AppsFileImporter:
    """Copy registry YAML files and deploy pin texts into SQLite."""

    def __init__(self, home: Path) -> None:
        self._home = home
        self._registry = home / REGISTRY_DIR

    def import_into(self, session: Session) -> int:
        count = 0
        for path in self._manifest_paths():
            if self._import_one(session, path):
                count += 1
        self._import_deploy_pins(session)
        return count

    def _manifest_paths(self) -> list[Path]:
        if not self._registry.is_dir():
            return []
        found: list[Path] = []
        for child in sorted(self._registry.iterdir()):
            if not child.is_dir():
                continue
            manifest = child / APP_MANIFEST_FILENAME
            if manifest.is_file():
                found.append(manifest)
        return found

    def _import_one(self, session: Session, path: Path) -> bool:
        text = self._read_text(path)
        if text is None:
            return False
        parsed = self._try_parse(path, text)
        if parsed is None:
            return False
        app, api_version, kind = parsed
        self._upsert_app(session, app, api_version, kind, text)
        return True

    @staticmethod
    def _upsert_app(session: Session, app, api_version: str, kind: str, text: str) -> None:
        identity = AppSourceIdentity.from_app(app)
        fields = dict(
            api_version=api_version,
            kind=kind,
            manifest_yaml=text,
            source_kind=identity.source,
            source_identity=identity.key,
            group_name=app.group,
        )
        row = session.get(AppRow, app.name)
        if row is None:
            session.add(AppRow(name=app.name, **fields))
            return
        for key, value in fields.items():
            setattr(row, key, value)

    def _import_deploy_pins(self, session: Session) -> None:
        if not self._registry.is_dir():
            return
        for child in sorted(self._registry.iterdir()):
            if not child.is_dir():
                continue
            self._upsert_pin(session, child.name)

    def _upsert_pin(self, session: Session, name: str) -> None:
        paths = ServicePaths(self._home, name)
        ref_text = self._read_text(paths.deploy_ref())
        image_text = self._read_text(paths.deploy_image())
        if ref_text is None and image_text is None:
            return
        row = session.get(DeployPinRow, name)
        if row is None:
            session.add(
                DeployPinRow(app_name=name, ref_text=ref_text, image_text=image_text)
            )
            return
        row.ref_text = ref_text
        row.image_text = image_text

    @staticmethod
    def _try_parse(path: Path, text: str):
        try:
            raw = yaml.safe_load(text) or {}
            if not isinstance(raw, dict):
                return None
            app, _ = AppDocument.parse(raw, path=path)
            api = str(raw.get("apiVersion") or CONTRACT_API_VERSION)
            kind = str(raw.get("kind") or CONTRACT_KIND)
            return app, api, kind
        except Exception:  # noqa: BLE001 — lenient like registry load
            return None

    @staticmethod
    def _read_text(path: Path) -> Optional[str]:
        if not path.is_file():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None
