"""Deferred import of one module attribute. The only ``importlib`` site in the CLI."""

from __future__ import annotations

import importlib
from typing import Any


class LazyImport:
    """Import ``module.attr`` on first call, then reuse that object."""

    def __init__(self, module: str, attr: str) -> None:
        self._module = module
        self._attr = attr
        self._obj: Any = None

    def _load(self) -> Any:
        if self._obj is None:
            mod = importlib.import_module(self._module)
            self._obj = getattr(mod, self._attr)
        return self._obj

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._load()(*args, **kwargs)
