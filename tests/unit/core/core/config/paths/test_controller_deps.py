"""ControllerDepsPyproject synthesis from installed distribution."""

from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

import raft.core.core.config.paths.controller_deps as controller_deps_mod
from raft.core.core.config.paths.controller_deps import ControllerDepsPyproject

from tests.unit.base import RaftTestCase


class TestControllerDepsPyproject(RaftTestCase):
    def test_write_requires_dist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dest = self.tmp_path / "pyproject.toml"

        def boom(_name: str):
            raise PackageNotFoundError("raft")

        monkeypatch.setattr(controller_deps_mod, "distribution_requires", boom)
        with pytest.raises(FileNotFoundError, match="pyproject.toml"):
            ControllerDepsPyproject().write_from_installed(dest)

    def test_write_skips_extras(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dest = self.tmp_path / "pyproject.toml"
        monkeypatch.setattr(
            controller_deps_mod,
            "distribution_requires",
            lambda _name: [
                "fire>=0.7.1",
                'pytest>=7.0; extra == "dev"',
                'PyYAML>=6.0; python_version >= "3.9"',
            ],
        )
        ControllerDepsPyproject().write_from_installed(dest)
        text = dest.read_text(encoding="utf-8")
        assert "fire>=0.7.1" in text
        assert "PyYAML>=6.0" in text
        assert "pytest" not in text

    def test_write_empty_requires(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dest = self.tmp_path / "pyproject.toml"
        monkeypatch.setattr(
            controller_deps_mod, "distribution_requires", lambda _name: []
        )
        with pytest.raises(FileNotFoundError, match="no requires"):
            ControllerDepsPyproject().write_from_installed(dest)

    def test_write_only_extras(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dest = self.tmp_path / "pyproject.toml"
        monkeypatch.setattr(
            controller_deps_mod,
            "distribution_requires",
            lambda _name: ['pytest>=7.0; extra == "dev"'],
        )
        with pytest.raises(FileNotFoundError, match="no main dependencies"):
            ControllerDepsPyproject().write_from_installed(dest)

    def test_find_raft_pyproject_skips_unrelated_toml(self) -> None:
        other = self.tmp_path / "other"
        other.mkdir()
        (other / "pyproject.toml").write_text(
            'name = "something-else"\n', encoding="utf-8"
        )
        nested = other / "share"
        nested.mkdir()
        assert ControllerDepsPyproject().find_raft_pyproject(nested) is None
