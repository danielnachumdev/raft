"""The only ``importlib`` site for CLI objects that must not load at startup."""

from __future__ import annotations

import importlib
from typing import Any, Collection, Mapping, Optional


class LazyImportManager:
    """Resolve ``module:attr`` targets for CLI consumers.

    Consumers call :meth:`get`, :meth:`call`, or :meth:`command`. They do not
    import the registered modules themselves.

    ``targets`` are classes and functions. ``commands`` are Fire groups, keyed
    by the CLI name (``alerts``, not ``AlertsCLI``). A command object keeps the
    registered docstring and imports its class on first attribute use.
    ``callable_commands`` (``raft events``) are constructed immediately so Fire
    sees the real ``__call__`` signature.
    """

    def __init__(
        self,
        targets: Mapping[str, str],
        commands: Optional[Mapping[str, tuple[str, str]]] = None,
        callable_commands: Optional[Collection[str]] = None,
    ) -> None:
        self._targets = dict(targets)
        self._commands = dict(commands or {})
        self._callable = frozenset(callable_commands or ())
        unknown = self._callable - self._commands.keys()
        if unknown:
            raise ValueError(f"callable commands not in the registry: {sorted(unknown)}")
        self._cache: dict[str, Any] = {}

    def get(self, name: str) -> Any:
        """Return the object registered under ``name``, importing it once."""
        cached = self._cache.get(name)
        if cached is not None:
            return cached
        spec = self._targets.get(name)
        if spec is None:
            raise KeyError(name)
        value = self._resolve(spec)
        self._cache[name] = value
        return value

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Call the object registered under ``name``."""
        return self.get(name)(*args, **kwargs)

    def command_names(self) -> frozenset[str]:
        """Fire group names that :meth:`command` can build."""
        return frozenset(self._commands)

    def command(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Build one Fire group. Import stays deferred until the group is used."""
        spec_doc = self._commands.get(name)
        if spec_doc is None:
            raise KeyError(name)
        spec, doc = spec_doc
        if name in self._callable:
            return self._resolve(spec)(*args, **kwargs)
        return _DeferredCommand(self, spec, doc, args, kwargs)

    @staticmethod
    def _resolve(spec: str) -> Any:
        module_name, attr = spec.split(":", 1)
        module = importlib.import_module(module_name)
        return getattr(module, attr)


class _DeferredCommand:
    """Fire group stand-in. The registered class is imported on first use."""

    def __init__(
        self,
        manager: LazyImportManager,
        spec: str,
        doc: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        self._manager = manager
        self._spec = spec
        self._args = args
        self._kwargs = kwargs
        self._obj: Any = None
        self.__doc__ = doc

    def _target(self) -> Any:
        if self._obj is None:
            self._obj = self._manager._resolve(self._spec)(*self._args, **self._kwargs)
        return self._obj

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target(), name)

    def __dir__(self) -> list[str]:
        return dir(self._target())
