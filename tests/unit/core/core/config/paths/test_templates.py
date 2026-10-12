"""Product template sync coverage."""

from pathlib import Path

import pytest

from raft.core.core.config import (
    ensure_raft_home,
    find_package_root,
    sync_product_templates,
)
from raft.core.core.config.paths.templates import ProductTemplateSync

from tests.unit.base import RaftTestCase


class TestProductTemplateSync(RaftTestCase):
    def test_sync_replaces_existing_controller_package(self) -> None:
        home = self.tmp_path / "home"
        ensure_raft_home(home)
        marker = home / "controller" / "raft" / "stale-marker"
        marker.write_text("old\n", encoding="utf-8")
        ProductTemplateSync()._sync_controller_package(home, find_package_root())
        assert not marker.is_file()
        assert (home / "controller" / "raft" / "__init__.py").is_file()

    def test_find_package_root_bundled(self) -> None:
        root = find_package_root()
        assert (root / "compose.yaml").is_file()
        assert (root / "nginx").is_dir()

    def test_sync_missing_file_template(self) -> None:
        empty = self.tmp_path / "empty-pkg"
        empty.mkdir()
        with pytest.raises(FileNotFoundError, match="missing package template"):
            sync_product_templates(self.tmp_path / "dest", empty)

    def test_sync_missing_dir_template(self) -> None:
        pkg = self.tmp_path / "partial-pkg"
        pkg.mkdir()
        (pkg / "compose.yaml").write_text("name: raft\n", encoding="utf-8")
        dest = self.tmp_path / "dest"
        dest.mkdir()
        with pytest.raises(FileNotFoundError, match="missing package template dir"):
            sync_product_templates(dest, pkg)

    def test_sync_skips_controller_package_without_parent_init(self) -> None:
        pkg = self.tmp_path / "share-only"
        (pkg / "nginx").mkdir(parents=True)
        (pkg / "controller").mkdir()
        (pkg / "compose.yaml").write_text("name: raft\n", encoding="utf-8")
        (pkg / "controller" / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
        dest = self.tmp_path / "dest"
        dest.mkdir()
        sync_product_templates(dest, pkg)
        assert (dest / "controller" / "Dockerfile").is_file()
        assert not (dest / "controller" / "raft").exists()
        pyproject = dest / "controller" / "pyproject.toml"
        assert pyproject.is_file()
        text = pyproject.read_text(encoding="utf-8")
        assert "raft-controller-deps" in text
        assert "fire" in text and "PyYAML" in text

    def test_sync_controller_pyproject_keeps_existing_when_no_source(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = self.tmp_path / "home"
        dest = home / "controller" / "pyproject.toml"
        dest.parent.mkdir(parents=True)
        dest.write_text('name = "kept"\n', encoding="utf-8")
        syncer = ProductTemplateSync()
        monkeypatch.setattr(syncer._deps, "find_raft_pyproject", lambda _p: None)
        monkeypatch.setattr(
            syncer._deps, "write_from_installed", self._raise_no_dist
        )
        syncer._sync_controller_pyproject(home, self.tmp_path / "share")
        assert dest.read_text(encoding="utf-8") == 'name = "kept"\n'

    def test_sync_controller_pyproject_raises_when_nothing_to_keep(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = self.tmp_path / "home"
        syncer = ProductTemplateSync()
        monkeypatch.setattr(syncer._deps, "find_raft_pyproject", lambda _p: None)
        monkeypatch.setattr(
            syncer._deps, "write_from_installed", self._raise_no_dist
        )
        with pytest.raises(FileNotFoundError, match="no dist"):
            syncer._sync_controller_pyproject(home, self.tmp_path / "share")

    @staticmethod
    def _raise_no_dist(_dest: Path) -> None:
        raise FileNotFoundError("no dist")
