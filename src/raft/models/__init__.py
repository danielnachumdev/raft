"""Inventory-backed stack model."""

from .app import (
    COMPOSE_PROJECT,
    CONTROLLER_COMPOSE_ID,
    EDGE_GROUP,
    GATE_COMPOSE_ID,
    ROUTER_COMPOSE_ID,
    App,
    compose_service_id,
    display_service_label,
)
from .app_document import AppDocument
from .graph_event import GraphEvent
from .graph_event_store import (
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
    GraphEventStore,
)
from .manifest import (
    CONTRACT_API_VERSION,
    CONTRACT_KIND,
    CONTRACT_REL_PATH,
    AppSpec,
    VolumeSpec,
)
from .ports import PortSpec, parse_ports
from .readiness_parser import parse_readiness
from .readiness_spec import ReadinessSpec
from .registry import AppRegistry
from .scaling_spec import ScalingSpec, ScalingSpecParser
from .stack import Stack, load_stack

__all__ = [
    "COMPOSE_PROJECT",
    "CONTRACT_API_VERSION",
    "CONTRACT_KIND",
    "CONTRACT_REL_PATH",
    "CONTROLLER_COMPOSE_ID",
    "EDGE_GROUP",
    "GATE_COMPOSE_ID",
    "ROUTER_COMPOSE_ID",
    "App",
    "AppDocument",
    "AppRegistry",
    "AppSpec",
    "GraphEvent",
    "GraphEventStore",
    "KIND_DEPLOYMENT",
    "KIND_DOWN",
    "KIND_GATE_RECREATE",
    "KIND_SCALING",
    "KIND_START",
    "KIND_STOP",
    "KIND_UP",
    "KIND_UPDATE",
    "SCALING_ACTION_IDLE_STOP",
    "SCALING_ACTION_WAKE",
    "VolumeSpec",
    "PortSpec",
    "ReadinessSpec",
    "ScalingSpec",
    "ScalingSpecParser",
    "Stack",
    "compose_service_id",
    "display_service_label",
    "load_stack",
    "parse_ports",
    "parse_readiness",
]
