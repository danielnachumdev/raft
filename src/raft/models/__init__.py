"""Inventory-backed stack model."""

from ..config.paths import ensure_raft_home, find_package_root, raft_home
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
    "VolumeSpec",
    "PortSpec",
    "ReadinessSpec",
    "Stack",
    "compose_service_id",
    "display_service_label",
    "ensure_raft_home",
    "find_package_root",
    "load_stack",
    "parse_ports",
    "parse_readiness",
    "raft_home",
]
