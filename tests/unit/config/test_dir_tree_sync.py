"""DirTreeSync preserves destination inodes (Docker bind-mount safety)."""

from __future__ import annotations

from pathlib import Path

from raft.config.dir_tree_sync import DirTreeSync
from raft.config.paths import ensure_raft_home, find_package_root, sync_product_templates

from ..base import RaftTestCase


class TestDirTreeSync(RaftTestCase):
    def test_sync_preserves_dest_dir_inode(self) -> None:
        src = self._tree("src", {"a.txt": "one", "sub/b.txt": "two"})
        dest = self.tmp_path / "dest"
        sync = DirTreeSync()
        sync.sync(src, dest)
        inode = dest.stat().st_ino
        (src / "a.txt").write_text("updated\n", encoding="utf-8")
        sync.sync(src, dest)
        assert dest.stat().st_ino == inode
        assert (dest / "a.txt").read_text(encoding="utf-8") == "updated\n"
        assert (dest / "sub" / "b.txt").read_text(encoding="utf-8") == "two"

    def test_sync_removes_stale_entries(self) -> None:
        src = self._tree("src", {"keep.txt": "ok"})
        dest = self._tree("dest", {"keep.txt": "old", "gone.txt": "x", "old/x.txt": "y"})
        DirTreeSync().sync(src, dest)
        assert (dest / "keep.txt").read_text(encoding="utf-8") == "ok"
        assert not (dest / "gone.txt").exists()
        assert not (dest / "old").exists()

    def test_sync_skips_broken_symlinks(self) -> None:
        src = self.tmp_path / "src"
        dest = self.tmp_path / "dest"
        src.mkdir()
        (src / "broken").symlink_to("missing-target")
        DirTreeSync().sync(src, dest)
        assert dest.is_dir()
        assert not (dest / "broken").exists()

    def test_product_templates_preserve_nginx_errors_inode(self) -> None:
        home = self.tmp_path / "home"
        ensure_raft_home(home)
        errors = home / "nginx" / "errors"
        inode = errors.stat().st_ino
        stale = errors / "stale-operator.html"
        stale.write_text("stale\n", encoding="utf-8")
        sync_product_templates(home, find_package_root())
        assert errors.stat().st_ino == inode
        assert (errors / "holding.html").is_file()
        assert not stale.exists()

    def _tree(self, name: str, files: dict) -> Path:
        root = self.tmp_path / name
        for rel, body in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        return root
