"""Product template sync coverage."""

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

import pytest

from raft.core.core.config import (
    ensure_raft_home,
    find_package_root,
    sync_product_templates,
)
from raft.core.core.config.paths.constants import CONTROLLER_BUILD_DIR
from raft.core.core.config.paths.templates import ProductTemplateSync

from tests.unit.base import RaftTestCase


@contextmanager
def _installed_version(package: str, detail: str) -> Iterator[None]:
    with patch(
        "raft.core.core.config.paths.templates.InstalledVersion.package_version",
        return_value=package,
    ), patch(
        "raft.core.core.config.paths.templates.InstalledVersion.source_detail",
        return_value=detail,
    ):
        yield


class TestProductTemplateSync(RaftTestCase):
    def test_sync_replaces_existing_controller_package_when_stamp_missing(self) -> None:
        home = self.tmp_path / "home"
        ensure_raft_home(home)
        package = home / "controller" / "raft"
        stamp = package / "_install_stamp.json"
        assert stamp.is_file()
        stamp.unlink()
        marker = package / "stale-marker"
        marker.write_text("old\n", encoding="utf-8")
        ProductTemplateSync()._sync_python_build(
            home, find_package_root(), CONTROLLER_BUILD_DIR
        )
        assert not marker.is_file()
        assert (package / "__init__.py").is_file()
        assert stamp.is_file()

    def test_sync_python_build_skips_recopy_when_stamp_matches(self) -> None:
        home = self.tmp_path / "home"
        ensure_raft_home(home)
        root = find_package_root()
        syncer = ProductTemplateSync()
        syncer._sync_python_build(home, root, CONTROLLER_BUILD_DIR)
        marker = home / "controller" / "raft" / "sync-skip-marker"
        marker.write_text("keep\n", encoding="utf-8")
        syncer._sync_python_build(home, root, CONTROLLER_BUILD_DIR)
        assert marker.is_file()
        assert marker.read_text(encoding="utf-8") == "keep\n"
        assert (home / "controller" / "raft" / "__init__.py").is_file()

    def test_full_sync_keeps_stamped_package_tree(self) -> None:
        home = self.tmp_path / "home"
        ensure_raft_home(home)
        root = find_package_root()
        ProductTemplateSync().sync(home, root)
        marker = home / "controller" / "raft" / "full-sync-marker"
        marker.write_text("keep\n", encoding="utf-8")
        ProductTemplateSync().sync(home, root)
        assert marker.is_file()
        assert marker.read_text(encoding="utf-8") == "keep\n"

    def test_sync_python_build_recopies_when_stamp_changes(self) -> None:
        home = self.tmp_path / "home"
        ensure_raft_home(home)
        root = find_package_root()
        syncer = ProductTemplateSync()
        self._sync_with_version(syncer, home, root, "0.12.7")
        marker = home / "controller" / "raft" / "sync-skip-marker"
        marker.write_text("stale\n", encoding="utf-8")
        self._sync_with_version(syncer, home, root, "0.12.8")
        assert not marker.is_file()
        assert (home / "controller" / "raft" / "__init__.py").is_file()
        text = (home / "controller" / "raft" / "_install_stamp.json").read_text(
            encoding="utf-8"
        )
        assert '"package": "0.12.8"' in text
        assert "raft-0.12.8-py3-none-any.whl" in text

    def test_sync_stamps_host_version_into_python_builds(self) -> None:
        home = self.tmp_path / "home"
        ensure_raft_home(home)
        with _installed_version("0.12.7", "wheel raft-0.12.7-py3-none-any.whl"):
            ProductTemplateSync().sync(home, find_package_root())
        for build in ("controller", "dashboard"):
            stamp = home / build / "raft" / "_install_stamp.json"
            assert stamp.is_file(), build
            text = stamp.read_text(encoding="utf-8")
            assert '"package": "0.12.7"' in text
            assert "raft-0.12.7-py3-none-any.whl" in text

    @staticmethod
    def _sync_with_version(
        syncer: ProductTemplateSync, home: Path, root: Path, package: str
    ) -> None:
        detail = f"wheel raft-{package}-py3-none-any.whl"
        with _installed_version(package, detail):
            syncer._sync_python_build(home, root, CONTROLLER_BUILD_DIR)

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
        (pkg / "nginx").mkdir(parents=True, exist_ok=True)
        (pkg / "controller").mkdir()
        (pkg / "dashboard").mkdir()
        (pkg / "compose.yaml").write_text("name: raft\n", encoding="utf-8")
        (pkg / "controller" / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
        (pkg / "dashboard" / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
        dest = self.tmp_path / "dest"
        dest.mkdir()
        sync_product_templates(dest, pkg)
        assert (dest / "controller" / "Dockerfile").is_file()
        assert (dest / "dashboard" / "Dockerfile").is_file()
        assert not (dest / "controller" / "raft").exists()
        assert not (dest / "dashboard" / "raft").exists()
        pyproject = dest / "controller" / "pyproject.toml"
        assert pyproject.is_file()
        text = pyproject.read_text(encoding="utf-8")
        assert "raft-controller-deps" in text
        assert "fire" in text and "PyYAML" in text

    def test_sync_build_pyproject_keeps_existing_when_no_source(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = self.tmp_path / "home"
        dest = home / "controller" / "pyproject.toml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text('name = "kept"\n', encoding="utf-8")
        syncer = ProductTemplateSync()
        monkeypatch.setattr(syncer._deps, "find_raft_pyproject", lambda _p: None)
        monkeypatch.setattr(
            syncer._deps, "write_from_installed", self._raise_no_dist
        )
        syncer._sync_build_pyproject(
            home, self.tmp_path / "share", CONTROLLER_BUILD_DIR
        )
        assert dest.read_text(encoding="utf-8") == 'name = "kept"\n'

    def test_sync_build_pyproject_raises_when_nothing_to_keep(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = self.tmp_path / "home"
        syncer = ProductTemplateSync()
        monkeypatch.setattr(syncer._deps, "find_raft_pyproject", lambda _p: None)
        monkeypatch.setattr(
            syncer._deps, "write_from_installed", self._raise_no_dist
        )
        with pytest.raises(FileNotFoundError, match="no dist"):
            syncer._sync_build_pyproject(
                home, self.tmp_path / "share", CONTROLLER_BUILD_DIR
            )

    @staticmethod
    def _raise_no_dist(_dest: Path) -> None:
        raise FileNotFoundError("no dist")
