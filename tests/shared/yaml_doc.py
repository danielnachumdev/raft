"""Load / merge / dump YAML documents for e2e and registry patching."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional

import yaml


class YamlDoc:
    """In-place YAML file edits without repeating load/dump boilerplate."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> MutableMapping[str, Any]:
        data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        assert isinstance(data, dict)
        return data

    def dump(self, data: Mapping[str, Any]) -> None:
        self.path.write_text(
            yaml.safe_dump(dict(data), sort_keys=False), encoding="utf-8"
        )

    def merge_root(self, key: str, value: Any) -> MutableMapping[str, Any]:
        data = self.load()
        data[key] = value
        self.dump(data)
        return data

    def merge_spec(self, patch: Mapping[str, Any]) -> MutableMapping[str, Any]:
        data = self.load()
        spec = data.setdefault("spec", {})
        assert isinstance(spec, dict)
        spec.update(patch)
        self.dump(data)
        return data

    def replace(self, data: Optional[Mapping[str, Any]] = None, **kwargs: Any) -> None:
        doc = dict(data or self.load())
        doc.update(kwargs)
        self.dump(doc)
