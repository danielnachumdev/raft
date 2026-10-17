"""Load firewall documents from YAML/JSON files for CLI."""

import json
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml

from raft.core.core.errors.cta import OperatorError


class FirewallCliIo:
    """Read operator-supplied firewall YAML/JSON files."""

    def read_mapping(self, file: str) -> Mapping[str, Any]:
        path = Path(file)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise OperatorError(
                f"cannot read {file}: {exc}.\nFix: provide a readable file path"
            ) from exc
        return self._parse(text, path=file)

    def dump(self, payload: Any, *, as_json: bool) -> str:
        if as_json:
            return json.dumps(payload, indent=2, sort_keys=False) + "\n"
        return yaml.safe_dump(payload, sort_keys=False)

    def _parse(self, text: str, *, path: str) -> Mapping[str, Any]:
        raw = self._loads(text, path=path)
        if not isinstance(raw, dict):
            raise OperatorError(
                f"{path} must be a mapping document.\n"
                f"Fix: use a YAML/JSON object with version + rules"
            )
        return raw

    @staticmethod
    def _loads(text: str, *, path: str) -> Any:
        stripped = text.lstrip()
        try:
            if stripped.startswith("{"):
                return json.loads(text)
            return yaml.safe_load(text) or {}
        except (json.JSONDecodeError, yaml.YAMLError) as exc:
            raise OperatorError(
                f"cannot parse {path}: {exc}.\nFix: provide valid YAML or JSON"
            ) from exc

    @staticmethod
    def require_file(file: Optional[str], *, command: str) -> str:
        if not (file or "").strip():
            raise OperatorError(
                f"--file is required.\nFix: raft firewall {command} --file rules.yaml"
            )
        return file.strip()
