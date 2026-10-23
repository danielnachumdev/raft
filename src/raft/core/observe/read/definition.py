"""Applied App manifest YAML for serve service diagnostics."""

from pathlib import Path
from typing import Any, Dict, Optional

from raft.core.core.config.paths.service_paths import ServicePaths
from raft.core.core.models.app import (
    CONTROLLER_COMPOSE_ID,
    DASHBOARD_COMPOSE_ID,
    GATE_COMPOSE_ID,
    ROUTER_COMPOSE_ID,
    App,
)
from raft.core.core.models.stack import Stack

_EDGE_IDS = frozenset(
    {GATE_COMPOSE_ID, ROUTER_COMPOSE_ID, CONTROLLER_COMPOSE_ID, DASHBOARD_COMPOSE_ID}
)
_EDGE_ALIASES = {
    "gate": GATE_COMPOSE_ID,
    "router": ROUTER_COMPOSE_ID,
    "controller": CONTROLLER_COMPOSE_ID,
    "dashboard": DASHBOARD_COMPOSE_ID,
}


class AppDefinitionRead:
    """Return durable ``services/<name>/app.yaml`` text for one Compose service."""

    def __init__(self, stack: Stack) -> None:
        self.stack = stack

    def for_service(self, name: str) -> Dict[str, Any]:
        key = name.strip()
        edge_id = _EDGE_ALIASES.get(key, key if key in _EDGE_IDS else None)
        if edge_id is not None:
            return self._ineligible(
                edge_id,
                "edge and control-plane services have no applied App manifest",
            )
        app = self._find_app(key)
        if app is None:
            return {
                "service": key,
                "app": None,
                "path": None,
                "yaml": None,
                "eligible": False,
                "reason": f"unknown service '{key}'",
                "unknown": True,
            }
        return self._for_app(app)

    def bind_stack(self, stack: Stack) -> None:
        self.stack = stack

    def _for_app(self, app: App) -> Dict[str, Any]:
        path = ServicePaths(self.stack.root, app.name).app_yaml()
        rel = self._relative(path)
        text = self._read_yaml(path)
        if text is None:
            return self._ineligible(
                app.compose_id,
                f"applied manifest missing at {rel}",
                app=app.name,
                path=rel,
            )
        return {
            "service": app.compose_id,
            "app": app.name,
            "path": rel,
            "yaml": text,
            "eligible": True,
            "reason": None,
        }

    def _find_app(self, key: str) -> Optional[App]:
        for app in self.stack.apps:
            if app.name == key or app.compose_id == key:
                return app
        return None

    def _read_yaml(self, path: Path) -> Optional[str]:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def _relative(self, path: Path) -> str:
        return str(path.relative_to(self.stack.root))

    @staticmethod
    def _ineligible(
        compose_id: str,
        reason: str,
        *,
        app: Optional[str] = None,
        path: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "service": compose_id,
            "app": app,
            "path": path,
            "yaml": None,
            "eligible": False,
            "reason": reason,
        }
