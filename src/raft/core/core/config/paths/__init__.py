"""Durable operator home under ``~/.raft/`` (override with ``RAFT_DATA_HOME``)."""

from pathlib import Path
from typing import Optional

from .bootstrap import RaftHomeBootstrap
from .constants import (
    APPS_DIRNAME,
    CERTS_DIRNAME,
    CHECKOUT_DIRNAME,
    CONTROLLER_BUILD_DIR,
    CONTROLLER_PACKAGE_DIR,
    CONTROLLER_PYPROJECT,
    DATA_DIR_RELS,
    DATA_HOME_ENV,
    DB_FILENAME,
    DEPLOY_DIRNAME,
    GENERATED_DIRNAME,
    HOST_DIRNAME,
    LOCKS_DIR,
    LOGS_DIRNAME,
    SERVICES_DIRNAME,
    SETTINGS_FILENAME,
    STATE_DIR,
    TEMPLATE_DIRS,
    TEMPLATE_FILES,
)
from .dir_tree_sync import DirTreeSync
from .home import RaftHome
from .host_paths import HostPaths
from .package_root import PackageRootFinder
from .service_paths import ServicePaths
from .templates import ProductTemplateSync

__all__ = [
    "APPS_DIRNAME",
    "CERTS_DIRNAME",
    "CHECKOUT_DIRNAME",
    "CONTROLLER_BUILD_DIR",
    "CONTROLLER_PACKAGE_DIR",
    "CONTROLLER_PYPROJECT",
    "DATA_DIR_RELS",
    "DATA_HOME_ENV",
    "DB_FILENAME",
    "DEPLOY_DIRNAME",
    "DirTreeSync",
    "GENERATED_DIRNAME",
    "HOST_DIRNAME",
    "HostPaths",
    "LOCKS_DIR",
    "LOGS_DIRNAME",
    "PackageRootFinder",
    "ProductTemplateSync",
    "RaftHome",
    "RaftHomeBootstrap",
    "SERVICES_DIRNAME",
    "SETTINGS_FILENAME",
    "STATE_DIR",
    "ServicePaths",
    "TEMPLATE_DIRS",
    "TEMPLATE_FILES",
    "ensure_raft_home",
    "find_package_root",
    "raft_home",
    "settings_path",
    "sync_product_templates",
]


def raft_home() -> Path:
    return RaftHome().resolve()


def settings_path(home: Optional[Path] = None) -> Path:
    return RaftHome().settings_path(home)


def find_package_root(start: Optional[Path] = None) -> Path:
    return PackageRootFinder().find(start)


def ensure_raft_home(
    home: Optional[Path] = None,
    *,
    package_root: Optional[Path] = None,
) -> Path:
    return RaftHomeBootstrap().ensure(home, package_root=package_root)


def sync_product_templates(home: Path, package_root: Path) -> None:
    ProductTemplateSync().sync(home, package_root)
