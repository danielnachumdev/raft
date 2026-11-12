"""Sync packaged Compose/nginx/controller/dashboard templates into the data home."""

import errno
import shutil
from pathlib import Path

from raft.core.observe.ops.version import InstallStamp, InstalledVersion

from .bind_mount_fs import BindMountFs
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

_RO_ERRNOS = frozenset({errno.EROFS, errno.EACCES, errno.EPERM})


class ProductTemplateSync:
    """Copy product templates into ``~/.raft`` without breaking bind-mount inodes."""

    def __init__(self) -> None:
        self._tree = DirTreeSync()
        self._deps = ControllerDepsPyproject()
        self._fs = BindMountFs()

    def sync(self, home: Path, package_root: Path) -> None:
        for name in TEMPLATE_FILES:
            src = package_root / name
            if not src.is_file():
                raise FileNotFoundError(f"missing package template: {src}")
            self._fs.copy_file(src, home / name)
        for name in TEMPLATE_DIRS:
            src = package_root / name
            if not src.is_dir():
                raise FileNotFoundError(f"missing package template dir: {src}")
            # Build dirs hold a stamped ``raft/`` package copy that is not in the
            # share templates; keep it so stamp skip can work on the next sync.
            keep = (
                frozenset({CONTROLLER_PACKAGE_DIR})
                if name in (CONTROLLER_BUILD_DIR, DASHBOARD_BUILD_DIR)
                else None
            )
            self._tree.sync(src, home / name, keep=keep)
        self._sync_python_build(home, package_root, CONTROLLER_BUILD_DIR)
        self._sync_python_build(home, package_root, DASHBOARD_BUILD_DIR)

    def _sync_python_build(
        self, home: Path, package_root: Path, build_dir: str
    ) -> None:
        raft_src = package_root.parents[2]  # share → platform → core → raft
        if (raft_src / "__init__.py").is_file():
            dest = home / build_dir / CONTROLLER_PACKAGE_DIR
            if not self._installed_stamp_matches(dest):
                self._replace_python_tree(raft_src, dest)
        self._sync_build_pyproject(home, package_root, build_dir)

    def _replace_python_tree(self, raft_src: Path, dest: Path) -> None:
        try:
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(
                raft_src,
                dest,
                ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", "*.pyo", ".pytest_cache"
                ),
            )
            self._stamp_installed_version(dest)
        except OSError as exc:
            if dest.is_dir() and exc.errno in _RO_ERRNOS:
                return
            raise

    @staticmethod
    def _installed_stamp_matches(package_dir: Path) -> bool:
        """True when ``package_dir`` already has the stamp this process would write."""
        existing = InstallStamp().read(package_dir)
        if existing is None:
            return False
        expected = InstalledVersion().stamp_fields()
        if not expected.get("package"):
            return False
        return existing == expected

    @staticmethod
    def _stamp_installed_version(package_dir: Path) -> None:
        """Record host ``raft version`` so PYTHONPATH images match the CLI."""
        InstalledVersion().write_install_stamp(package_dir)

    def _sync_build_pyproject(
        self, home: Path, package_root: Path, build_dir: str
    ) -> None:
        dest_dir = home / build_dir
        self._fs.mkdir(dest_dir)
        dest = dest_dir / CONTROLLER_PYPROJECT
        src = self._deps.find_raft_pyproject(package_root)
        if src is not None:
            self._fs.copy_file(src, dest)
            return
        try:
            self._deps.write_from_installed(dest)
        except FileNotFoundError:
            if dest.is_file():
                return
            raise
        except OSError as exc:
            if dest.is_file() and exc.errno in _RO_ERRNOS:
                return
            raise
