"""Inventory-backed stack model."""

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
    COMPOSE_PROJECT,
    App,
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
    "find_repo_root",
    "load_app_file",
    "load_contract",
    "load_inventory",
    "load_registry",
    "load_stack",
    "registry_path",
]
