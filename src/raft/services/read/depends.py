"""Resolve App ``spec.dependsOn`` into Compose service ids for serve tables."""

from __future__ import annotations

from typing import Dict, Tuple

from ...errors import OperatorError
from ...models import App, Stack


class ServeDependsMap:
    """Map Compose service id → direct ``dependsOn`` Compose service ids."""

    def __init__(self, stack: Stack) -> None:
        self._by_name = {app.name: app for app in stack.apps}
        self._edges = self._build(stack)

    def for_service(self, compose_id: str) -> Tuple[str, ...]:
        return self._edges.get(compose_id, ())

    def _build(self, stack: Stack) -> Dict[str, Tuple[str, ...]]:
        return {app.compose_id: self._deps_for(stack, app) for app in stack.apps}

    def _deps_for(self, stack: Stack, app: App) -> Tuple[str, ...]:
        try:
            names = stack.spec_for(app).depend_names()
        except (OSError, ValueError, KeyError, TypeError, OperatorError):
            return ()
        out: list[str] = []
        for name in names:
            dep = self._by_name.get(name)
            if dep is not None:
                out.append(dep.compose_id)
        return tuple(out)
