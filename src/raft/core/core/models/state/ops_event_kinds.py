"""Kind constants and GraphEvent → OpsEvent mapping for dual-write (#267)."""

from typing import Optional

from .graph_event import GraphEvent
from .graph_event_kinds import (
    KIND_DEPLOYMENT,
    KIND_DOWN,
    KIND_GATE_RECREATE,
    KIND_SCALING,
    KIND_START,
    KIND_STOP,
    KIND_UP,
    KIND_UPDATE,
    SCALING_ACTION_IDLE_STOP,
    SCALING_ACTION_WAKE,
)

KIND_DEPLOY_APPLY = "deploy.apply"
KIND_DEPLOY_REDEPLOY = "deploy.redeploy"
KIND_STACK_PURGE = "stack.purge"
KIND_FIREWALL_APPLY = "firewall.apply"
KIND_GATE_RELOAD = "gate.reload"
KIND_GATE_RECREATE = "gate.recreate"
KIND_SCALE_WAKE = "scale.wake"
KIND_SCALE_IDLE_STOP = "scale.idle_stop"
KIND_ALERT_FIRED = "alert.fired"
KIND_ALERT_RESOLVED = "alert.resolved"
KIND_SERVICE_START = "service.start"
KIND_SERVICE_STOP = "service.stop"
KIND_STACK_UP = "stack.up"
KIND_STACK_DOWN = "stack.down"
KIND_RAFT_UPDATE = "raft.update"

DEPLOY_ACTION_APPLY = "apply"
DEPLOY_ACTION_REDEPLOY = "redeploy"

DEFAULT_OPS_RETENTION_MAX_AGE_DAYS = 14
DEFAULT_OPS_RETENTION_MAX_BYTES = 5 * 1024 * 1024


class OpsKindFromGraph:
    """Map a GraphEvent onto an ops journal kind (dual-write)."""

    @staticmethod
    def map(event: GraphEvent) -> Optional[str]:
        if event.kind == KIND_DEPLOYMENT:
            return OpsKindFromGraph._deploy(event)
        if event.kind == KIND_SCALING:
            return OpsKindFromGraph._scaling(event)
        return _GRAPH_KIND_MAP.get(event.kind)

    @staticmethod
    def _deploy(event: GraphEvent) -> str:
        action = event.metadata.get("action")
        if action == DEPLOY_ACTION_REDEPLOY:
            return KIND_DEPLOY_REDEPLOY
        return KIND_DEPLOY_APPLY

    @staticmethod
    def _scaling(event: GraphEvent) -> Optional[str]:
        action = event.metadata.get("action")
        if action == SCALING_ACTION_WAKE:
            return KIND_SCALE_WAKE
        if action == SCALING_ACTION_IDLE_STOP:
            return KIND_SCALE_IDLE_STOP
        return None


_GRAPH_KIND_MAP = {
    KIND_STOP: KIND_SERVICE_STOP,
    KIND_START: KIND_SERVICE_START,
    KIND_UP: KIND_STACK_UP,
    KIND_DOWN: KIND_STACK_DOWN,
    KIND_UPDATE: KIND_RAFT_UPDATE,
    KIND_GATE_RECREATE: KIND_GATE_RECREATE,
}
