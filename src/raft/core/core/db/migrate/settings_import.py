"""Import ``host/settings.yaml`` into the settings singleton row."""

from pathlib import Path
from typing import Any, Optional

import yaml
from sqlalchemy.orm import Session

from raft.core.core.config.paths.home import RaftHome
from raft.core.core.db.models.settings import SETTINGS_SINGLETON_ID, SettingsRow
from .json_util import MigrateJson


class SettingsFileImporter:
    """Load ``host/settings.yaml`` into ``settings`` (document JSON)."""

    def __init__(self, home: Path) -> None:
        self._home = home
        self._path = RaftHome().settings_path(home)

    def import_into(self, session: Session) -> bool:
        if not self._path.is_file():
            return False
        payload = self._read_mapping()
        if payload is None:
            return False
        row = session.get(SettingsRow, SETTINGS_SINGLETON_ID)
        text = MigrateJson.dumps(payload)
        if row is None:
            session.add(
                SettingsRow(
                    id=SETTINGS_SINGLETON_ID,
                    document_version=1,
                    payload_json=text,
                )
            )
        else:
            row.payload_json = text
            row.document_version = 1
        return True

    def _read_mapping(self) -> Optional[dict[str, Any]]:
        try:
            raw = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return None
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            return None
        return raw
