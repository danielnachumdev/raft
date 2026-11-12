"""In-place directory sync that preserves destination directory inodes.

Docker bind-mounts follow the mounted inode. ``rmtree`` + ``copytree`` replaces
that inode, so a running gate/router keeps serving an empty orphaned directory
(e.g. missing ``holding.html`` → nginx 404 for scaled-to-zero hosts).

Files already at ``dest`` with identical bytes are left in place. Read-only
bind mounts (dashboard ``.:/raft:ro``) skip mutative copies when the dest
already exists.
"""

from pathlib import Path
from typing import AbstractSet, Optional

from .bind_mount_fs import BindMountFs


class DirTreeSync:
    """Copy ``src`` onto ``dest`` without replacing ``dest`` itself."""

    def __init__(self) -> None:
        self._fs = BindMountFs()

    def sync(
        self,
        src: Path,
        dest: Path,
        *,
        keep: Optional[AbstractSet[str]] = None,
    ) -> None:
        self._fs.mkdir(dest)
        self._sync_contents(src, dest, keep=keep or frozenset())

    def _sync_contents(
        self, src: Path, dest: Path, *, keep: AbstractSet[str]
    ) -> None:
        wanted = {entry.name for entry in src.iterdir()} | set(keep)
        for entry in src.iterdir():
            self._sync_entry(entry, dest / entry.name)
        self._remove_extras(dest, wanted)

    def _sync_entry(self, src: Path, dest: Path) -> None:
        if src.is_dir():
            self.sync(src, dest)
            return
        if src.is_file():
            self._fs.copy_file(src, dest)

    def _remove_extras(self, dest: Path, wanted: set) -> None:
        for entry in list(dest.iterdir()):
            if entry.name in wanted:
                continue
            self._fs.remove(entry)
