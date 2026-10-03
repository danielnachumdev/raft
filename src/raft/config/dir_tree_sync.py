"""In-place directory sync that preserves destination directory inodes.

Docker bind-mounts follow the mounted inode. ``rmtree`` + ``copytree`` replaces
that inode, so a running gate/router keeps serving an empty orphaned directory
(e.g. missing ``holding.html`` → nginx 404 for scaled-to-zero hosts).
"""

from __future__ import annotations

import shutil
from pathlib import Path


class DirTreeSync:
    """Copy ``src`` onto ``dest`` without replacing ``dest`` itself."""

    def sync(self, src: Path, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        self._sync_contents(src, dest)

    def _sync_contents(self, src: Path, dest: Path) -> None:
        wanted = {entry.name for entry in src.iterdir()}
        for entry in src.iterdir():
            self._sync_entry(entry, dest / entry.name)
        self._remove_extras(dest, wanted)

    def _sync_entry(self, src: Path, dest: Path) -> None:
        if src.is_dir():
            self.sync(src, dest)
            return
        if src.is_file():
            shutil.copy2(src, dest)

    @staticmethod
    def _remove_extras(dest: Path, wanted: set) -> None:
        for entry in list(dest.iterdir()):
            if entry.name in wanted:
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
