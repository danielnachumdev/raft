"""Filesystem helpers that tolerate Docker read-only bind mounts."""

import errno
import filecmp
import shutil
from pathlib import Path

_RO_ERRNOS = frozenset({errno.EROFS, errno.EACCES, errno.EPERM})


class BindMountFs:
    """Skip mutating RO bind mounts when the destination already exists."""

    def mkdir(self, path: Path) -> None:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            if path.is_dir() and exc.errno in _RO_ERRNOS:
                return
            raise

    def copy_file(self, src: Path, dest: Path) -> None:
        if dest.is_file() and filecmp.cmp(src, dest, shallow=False):
            return
        try:
            shutil.copy2(src, dest)
        except OSError as exc:
            if dest.is_file() and exc.errno in _RO_ERRNOS:
                return
            raise

    def remove(self, path: Path) -> None:
        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists() or path.is_symlink():
                path.unlink()
        except OSError as exc:
            if exc.errno in _RO_ERRNOS:
                return
            raise
