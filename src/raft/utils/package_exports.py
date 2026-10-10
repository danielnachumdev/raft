"""Lazy package attribute exports (``__getattr__``) to avoid import cycles."""

from __future__ import annotations

import importlib
from typing import Any, Dict, List, Tuple


class PackageExports:
    """Resolve ``__all__`` names from ``module:attr`` specs on first access."""

    def __init__(self, package: str, mapping: Dict[str, str]) -> None:
        self._package = package
        self._mapping = mapping

    def get(self, name: str) -> Any:
        spec = self._mapping.get(name)
        if spec is None:
            raise AttributeError(
                f"module {self._package!r} has no attribute {name!r}"
            )
        mod_name, attr = self._split(spec)
        mod = importlib.import_module(mod_name, self._package)
        return getattr(mod, attr)

    @staticmethod
    def _split(spec: str) -> Tuple[str, str]:
        mod_name, attr = spec.split(":")
        return mod_name, attr
