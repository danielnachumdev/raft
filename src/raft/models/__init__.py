"""Inventory-backed stack model."""

from ..config.paths import ensure_raft_home, find_package_root, raft_home
from .app import COMPOSE_PROJECT, App
from .manifest import (
    CONTRACT_API_VERSION,
    CONTRACT_KIND,
    CONTRACT_REL_PATH,
    AppSpec,
    contract_path,
    load_app_file,
    load_contract,
    load_registry,
    registry_path,
)
from .ports import PortSpec, parse_ports
from .readiness import ReadinessSpec, parse_readiness
from .stack import Stack, load_stack

__all__ = [
    "COMPOSE_PROJECT",
    "CONTRACT_API_VERSION",
    "CONTRACT_KIND",
    "CONTRACT_REL_PATH",
    "App",
    "AppSpec",
    "PortSpec",
    "ReadinessSpec",
    "Stack",
    "contract_path",
    "ensure_raft_home",
    "find_package_root",
    "load_app_file",
    "load_contract",
    "load_registry",
    "load_stack",
    "parse_ports",
    "parse_readiness",
    "raft_home",
    "registry_path",
]
