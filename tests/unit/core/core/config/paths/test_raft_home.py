"""Raft data-home path and ensure bootstrap."""

from pathlib import Path

import pytest

from raft.core.core.config import ensure_raft_home, raft_home
from raft.core.core.config.paths.package_root import PackageRootFinder
from raft.core.core.errors.operator_error import OperatorError

from tests.unit.base import RaftTestCase
from .template_asserts import TemplateAsserts


class TestRaftHome(RaftTestCase, TemplateAsserts):
    def test_raft_home_env_and_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAFT_DATA_HOME", str(self.tmp_path / "custom"))
        assert raft_home() == (self.tmp_path / "custom").resolve()
        monkeypatch.delenv("RAFT_DATA_HOME", raising=False)
        assert raft_home() == (Path.home() / ".raft").resolve()

    def test_ensure_syncs_templates(self) -> None:
        home = self.tmp_path / "home"
        ensure_raft_home(home)
        self.assert_controller_templates(home)
        self.assert_compose_and_generated(home)
        ensure_raft_home(home)
        assert (home / "nginx" / "gate" / "nginx.conf").is_file()
        assert (
            home / "controller" / "raft" / "services" / "controller" / "__init__.py"
        ).is_file()

    def test_gate_nginx_conf_uses_builtin_stream(self) -> None:
        home = self.tmp_path / "home"
        ensure_raft_home(home)
        conf = (home / "nginx" / "gate" / "nginx.conf").read_text(encoding="utf-8")
        assert "load_module" not in conf
        assert "stream {" in conf
        assert "include /etc/nginx/stream-generated/*.conf;" in conf

    def test_find_package_root_via_module_parents(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        finder = PackageRootFinder()
        monkeypatch.setattr(finder, "_bundled_share", lambda: self.tmp_path / "nope")
        orphan = self.tmp_path / "orphan"
        orphan.mkdir()
        import raft.core.core.config.paths.package_root as package_root_mod

        pkg = Path(package_root_mod.__file__).resolve().parent

        def only_module_pkg(candidate: Path) -> bool:
            return candidate == pkg

        monkeypatch.setattr(finder, "_is_package_root", only_module_pkg)
        assert finder.find(orphan) == pkg

    def test_find_package_root_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        finder = PackageRootFinder()
        monkeypatch.setattr(finder, "_bundled_share", lambda: self.tmp_path / "nope")
        orphan = self.tmp_path / "orphan"
        orphan.mkdir()
        with pytest.raises(OperatorError, match="package templates"):
            finder.find(orphan)
