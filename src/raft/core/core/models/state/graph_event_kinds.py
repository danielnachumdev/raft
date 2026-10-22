"""Kind / action constants for GraphEvent JSONL records."""

from ..app import CONTROLLER_COMPOSE_ID, GATE_COMPOSE_ID, ROUTER_COMPOSE_ID
from .graph_event import GraphEvent

KIND_DEPLOYMENT = "deployment"
# Per-service power (distinct from stack KIND_UP / KIND_DOWN).
KIND_SERVICE_DOWN = "service_down"
KIND_SERVICE_UP = "service_up"
KIND_SCALING = "scaling"
KIND_UP = "up"
KIND_DOWN = "down"
KIND_UPDATE = "update"
KIND_GATE_REDEPLOY = "gate_redeploy"
SCALING_ACTION_IDLE_STOP = "idle_stop"
SCALING_ACTION_WAKE = "wake"
RAFT_LEVEL_SERVICES = frozenset(
    {GATE_COMPOSE_ID, ROUTER_COMPOSE_ID, CONTROLLER_COMPOSE_ID}
)
RAFT_LEVEL_KINDS = frozenset(
    {KIND_UP, KIND_DOWN, KIND_UPDATE, KIND_GATE_REDEPLOY}
)


class RaftLevelEvent:
    """Classify stack-wide / edge graph events for Trends filters."""

    @staticmethod
    def matches(event: GraphEvent) -> bool:
        """Stack-wide / edge events — always relevant on Trends (and Runtime)."""
        if event.service is None:
            return True
        if event.kind in RAFT_LEVEL_KINDS:
            return True
        return event.service in RAFT_LEVEL_SERVICES
