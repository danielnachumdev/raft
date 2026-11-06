"""Deferred import of one module attribute. The only ``importlib`` site in the CLI."""

from __future__ import annotations

import importlib
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


class LazyImport(Generic[T]):
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

    def __call__(self, *args: Any, **kwargs: Any) -> T:
        return self._load()(*args, **kwargs)


class FireLazyImportAdapter(Generic[T]):
    """Give Fire a group docstring without importing that group's module yet.

    Fire reads ``__doc__`` when it builds help. Constructing the real group
    (``AlertsCLI``, …) would import that module. This adapter holds the help
    text and a :class:`LazyImport` factory; the first attribute access
    constructs the real group and forwards to it.
    """

    def __init__(self, factory: Callable[..., T], stack: Any, doc: str) -> None:
        self._factory = factory
        self._stack = stack
        self._obj: T | None = None
        self.__doc__ = doc

    def _target(self) -> T:
        if self._obj is None:
            self._obj = self._factory(self._stack)
        return self._obj

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target(), name)

    def __dir__(self) -> list[str]:
        return dir(self._target())
