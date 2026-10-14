"""Map Compose ids / container names to retained service-log store keys."""

from typing import Optional

from raft.core.core.models.app import (
    COMPOSE_PROJECT,
    CONTROLLER_COMPOSE_ID,
    GATE_COMPOSE_ID,
    ROUTER_COMPOSE_ID,
)
from raft.core.core.models.stack import Stack

_EDGE = (GATE_COMPOSE_ID, ROUTER_COMPOSE_ID, CONTROLLER_COMPOSE_ID)


class ServiceLogsKeys:
    """Resolve logical store keys for apps + edge Compose services."""

    def __init__(self, stack: Stack) -> None:
        self.stack = stack

    def known_compose_ids(self, *, include_edge: bool = True) -> tuple[str, ...]:
        apps = tuple(app.compose_id for app in self.stack.apps)
        if not include_edge:
            return apps
        return _EDGE + apps

    def key_for_compose_id(self, compose_id: str) -> str:
        return compose_id

    def key_for_container_name(self, name: str) -> Optional[str]:
        """Map cutover tmp / compose-ish names to a store key when possible."""
        if not name:
            return None
        for app in self.stack.apps:
            if name == app.tmp_container or name == app.tmp_alias:
                return app.compose_id
        tmp_key = self._tmp_compose_id(name)
        if tmp_key is not None:
            return tmp_key
        if name in self.known_compose_ids(include_edge=True):
            return name
        return None

    @staticmethod
    def _tmp_compose_id(name: str) -> Optional[str]:
        prefix = f"{COMPOSE_PROJECT}-"
        if name.startswith(prefix) and name.endswith("_tmp"):
            return name[len(prefix) : -4] or None
        if name.endswith("_tmp"):
            return name[:-4] or None
        return None
