"""Sync packaged Compose/nginx/controller/dashboard templates into the data home."""

import shutil
from pathlib import Path

from .constants import (
    CONTROLLER_BUILD_DIR,
    CONTROLLER_PACKAGE_DIR,
    CONTROLLER_PYPROJECT,
    DASHBOARD_BUILD_DIR,
    TEMPLATE_DIRS,
    TEMPLATE_FILES,
)
from .controller_deps import ControllerDepsPyproject
from .dir_tree_sync import DirTreeSync


class ProductTemplateSync:
    """Copy product templates into ``~/.raft`` without breaking bind-mount inodes."""

    def __init__(self) -> None:
        self._tree = DirTreeSync()
        self._deps = ControllerDepsPyproject()

    def sync(self, home: Path, package_root: Path) -> None:
        for name in TEMPLATE_FILES:
            src = package_root / name
            if not src.is_file():
                raise FileNotFoundError(f"missing package template: {src}")
            shutil.copy2(src, home / name)
        for name in TEMPLATE_DIRS:
            src = package_root / name
            if not src.is_dir():
                raise FileNotFoundError(f"missing package template dir: {src}")
            self._tree.sync(src, home / name)
        self._sync_python_build(home, package_root, CONTROLLER_BUILD_DIR)
        self._sync_python_build(home, package_root, DASHBOARD_BUILD_DIR)

    def _sync_controller_package(self, home: Path, package_root: Path) -> None:
        """Backward-compatible name used by unit tests."""
        self._sync_python_build(home, package_root, CONTROLLER_BUILD_DIR)

    def _sync_controller_pyproject(self, home: Path, package_root: Path) -> None:
        """Backward-compatible name used by unit tests."""
        self._sync_build_pyproject(home, package_root, CONTROLLER_BUILD_DIR)

    def _sync_python_build(
        self, home: Path, package_root: Path, build_dir: str
    ) -> None:
        raft_src = package_root.parents[2]  # share → platform → core → raft
        if (raft_src / "__init__.py").is_file():
            dest = home / build_dir / CONTROLLER_PACKAGE_DIR
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(
                raft_src,
                dest,
                ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", "*.pyo", ".pytest_cache"
                ),
            )
        self._sync_build_pyproject(home, package_root, build_dir)

    def _sync_build_pyproject(
        self, home: Path, package_root: Path, build_dir: str
    ) -> None:
        dest_dir = home / build_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / CONTROLLER_PYPROJECT
        src = self._deps.find_raft_pyproject(package_root)
        if src is not None:
            shutil.copy2(src, dest)
            return
        try:
            self._deps.write_from_installed(dest)
        except FileNotFoundError:
            if dest.is_file():
                return
            raise
