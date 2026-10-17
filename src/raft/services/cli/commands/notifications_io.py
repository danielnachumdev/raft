"""Read YAML/JSON channel bodies for ``raft notifications``."""

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml

from raft.core.core.errors.cta import OperatorError


class NotificationsCliIo:
    """Load operator channel create/update payloads from disk."""

    def require_file(self, file: str, *, command: str) -> Path:
        path = Path(file).expanduser()
        if not path.is_file():
            raise OperatorError(
                f"notifications {command}: file not found: {path}\n"
                f"Fix: pass a YAML/JSON file "
                f"(e.g. id/type/settings for demo-api ops sinks)",
                has_fix=False,
            )
        return path

    def read_mapping(self, path: Path) -> Dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        raw = self._parse(text, path=path)
        if not isinstance(raw, dict):
            raise OperatorError(
                f"notifications file must be a YAML/JSON object: {path}\n"
                f"Fix: use {{id, type, settings?, enabled?}}",
                has_fix=False,
            )
        return dict(raw)

    def dump(self, payload: Mapping[str, Any], *, as_json: bool) -> str:
        if as_json:
            return json.dumps(dict(payload), indent=2, sort_keys=False) + "\n"
        return yaml.safe_dump(dict(payload), sort_keys=False)

    @staticmethod
    def _parse(text: str, *, path: Path) -> Any:
        stripped = text.lstrip()
        try:
            if stripped.startswith("{"):
                return json.loads(text)
            return yaml.safe_load(text)
        except (json.JSONDecodeError, yaml.YAMLError) as exc:
            raise OperatorError(
                f"cannot parse notifications file {path}: {exc}\n"
                f"Fix: provide valid YAML or JSON",
                has_fix=False,
            ) from exc

    def optional_settings(self, settings: Optional[str]) -> Optional[Dict[str, Any]]:
        if settings is None:
            return None
        try:
            raw = json.loads(settings)
        except json.JSONDecodeError as exc:
            raise OperatorError(
                "notifications --settings must be a JSON object.\n"
                'Fix: --settings \'{"url":"https://example.invalid/hook"}\'',
                has_fix=False,
            ) from exc
        if not isinstance(raw, dict):
            raise OperatorError(
                "notifications --settings must be a JSON object.\n"
                'Fix: --settings \'{"url":"https://example.invalid/hook"}\'',
                has_fix=False,
            )
        return dict(raw)
