"""Inventory-backed stack model."""

from ..config.paths import ensure_raft_home, find_package_root, raft_home
from .app import COMPOSE_PROJECT, App
from .contract import (
    CONTRACT_API_VERSION,
    CONTRACT_KINDS,
    CONTRACT_REL_PATH,
    ServiceContract,
    contract_path,
    load_app_file,
    load_contract,
    load_registry,
    registry_path,
)
from .inventory import (
    Stack,
    find_repo_root,
    load_inventory,
    load_stack,
)

__all__ = [
    "COMPOSE_PROJECT",
    "CONTRACT_API_VERSION",
    "CONTRACT_KINDS",
    "CONTRACT_REL_PATH",
    "App",
    "ServiceContract",
    "Stack",
    "contract_path",
    "ensure_raft_home",
    "find_package_root",
    "find_repo_root",
    "load_app_file",
    "load_contract",
    "load_inventory",
    "load_registry",
    "load_stack",
    "raft_home",
    "registry_path",
]
