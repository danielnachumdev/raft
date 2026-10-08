"""Stack helpers and package-root discovery."""

from pathlib import Path

import pytest

import raft.config.paths as paths
from raft.config.paths import find_package_root
from raft.models.ports import PortSpec
from raft.models.stack import load_stack

from ..base import RaftTestCase, make_app, write_inventory


class TestStack(RaftTestCase):
    @pytest.fixture(autouse=True)
    def _stack_setup(self, _raft_base) -> None:
        write_inventory(
            self.tmp_path,
            """
services:
  app:
    public_host: app.test
    source: local
    path: apps/app
""",
        )
        self.stack = load_stack(self.tmp_path)
        self.app = self.stack.app("app")

    def test_app_lookup_and_paths(self) -> None:
        port = PortSpec(name="http", container_port=80, expose="http")
        assert self.app.tmp_alias == "app_tmp"
        assert self.app.tmp_container == "raft-app_tmp"
        assert (
            self.stack.upstream_file(self.app, port)
            == self.tmp_path / "generated" / "nginx" / "upstreams" / "app-http.conf"
        )
        assert self.stack.upstream_name(self.app, port) == "app_http"
        assert self.stack.certs_dir == self.tmp_path / "certs"
        assert self.stack.core_services == (
            "raft-gate",
            "raft-router",
            "raft-controller",
            "app",
        )
        with pytest.raises(RuntimeError, match="unknown app"):
            self.stack.app("nope")

    def test_spec_for(self) -> None:
        spec = self.stack.spec_for(self.app)
        assert spec.ports[0].name == "http"
        assert self.stack.contract_for(self.app) is spec or True

    def test_image_and_ref_state_files(self) -> None:
        assert self.stack.image_state_file(self.app) == self.tmp_path / "deploy" / "app.image"
        assert self.stack.ref_state_file(self.app) == self.tmp_path / "deploy" / "app.ref"

    def test_load_stack_uses_raft_home_when_root_none(
        self, monkeypatch: pytest.MonkeyPatch, isolated_raft_data_home: Path
    ) -> None:
        write_inventory(
            isolated_raft_data_home,
            """
services:
  app:
    public_host: app.test
    source: local
    path: apps/app
""",
        )
        stack = load_stack(None)
        assert stack.root == isolated_raft_data_home.resolve()
        assert stack.app("app").name == "app"


class TestFindPackageRoot(RaftTestCase):
    def test_via_start_walk(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = self.tmp_path / "pkg"
        (fake / "nginx").mkdir(parents=True)
        (fake / "compose.yaml").write_text("name: raft\n", encoding="utf-8")
        monkeypatch.setattr(paths, "_bundled_share", lambda: self.tmp_path / "missing")
        nested = fake / "a" / "b"
        nested.mkdir(parents=True)
        assert find_package_root(nested) == fake.resolve()

    def test_via_package_parents(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pkg_root = self.tmp_path / "pkgroot"
        (pkg_root / "nginx").mkdir(parents=True)
        (pkg_root / "compose.yaml").write_text("name: raft\n", encoding="utf-8")
        fake_file = pkg_root / "raft" / "config" / "paths.py"
        fake_file.parent.mkdir(parents=True)
        fake_file.write_text("#\n", encoding="utf-8")
        orphan = self.tmp_path / "orphan"
        orphan.mkdir()
        monkeypatch.setattr(paths, "_bundled_share", lambda: self.tmp_path / "nope")
        monkeypatch.setattr(paths, "__file__", str(fake_file))
        assert find_package_root(orphan) == pkg_root.resolve()

    def test_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(paths, "_bundled_share", lambda: self.tmp_path / "nope")
        nested = self.tmp_path / "empty"
        nested.mkdir()
        with pytest.raises(RuntimeError, match="package templates"):
            find_package_root(nested)


class TestApp(RaftTestCase):
    def test_abs_path(self) -> None:
        app = make_app("d", public_host="d.example.com", path="apps/d")
        (self.tmp_path / "apps" / "d").mkdir(parents=True)
        assert app.abs_path(self.tmp_path) == (self.tmp_path / "apps" / "d").resolve()

    def test_display_service_label(self) -> None:
        from raft.models.app import (
            CONTROLLER_COMPOSE_ID,
            EDGE_GROUP,
            GATE_COMPOSE_ID,
            ROUTER_COMPOSE_ID,
            display_service_label,
        )

        assert display_service_label(GATE_COMPOSE_ID, EDGE_GROUP) == "gate"
        assert display_service_label(ROUTER_COMPOSE_ID, EDGE_GROUP) == "router"
        assert display_service_label(CONTROLLER_COMPOSE_ID, EDGE_GROUP) == "controller"
        assert display_service_label("demo-web", "demo") == "web"
        assert display_service_label("solo", None) == "solo"
        assert display_service_label("solo", "demo") == "solo"
        assert display_service_label("raft-gate", None) == "raft-gate"
