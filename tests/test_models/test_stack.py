"""Registry loading and Stack helpers."""

from pathlib import Path

import pytest

import raft.config.paths as paths
from raft.models import find_package_root, load_registry, load_stack
from raft.models.ports import PortSpec

from ..base import RaftTestCase, make_app, write_inventory


class TestLoadRegistry(RaftTestCase):
    def test_local_and_git(self) -> None:
        write_inventory(
            self.tmp_path,
            """
services:
  app:
    public_host: app.test
    source: local
    path: apps/app
  other:
    public_host: other.test
    source: git
    repo: "git@example.com:org/other.git"
    ref: develop
    path: apps/other
""",
        )
        apps = load_registry(self.tmp_path)
        assert len(apps) == 2
        assert apps[0].name == "app"
        assert apps[0].source == "local"
        assert apps[1].source == "git"
        assert apps[1].repo == "git@example.com:org/other.git"

    def test_rejects_git_without_repo(self) -> None:
        write_inventory(
            self.tmp_path,
            """
services:
  broken:
    public_host: broken.test
    source: git
""",
        )
        with pytest.raises(ValueError, match="repo is required"):
            load_registry(self.tmp_path)

    def test_rejects_bad_source(self) -> None:
        write_inventory(
            self.tmp_path,
            """
services:
  x:
    public_host: x.test
    source: s3
""",
        )
        with pytest.raises(ValueError, match="must be 'local', 'git', or 'docker'"):
            load_registry(self.tmp_path)

    def test_docker_source(self) -> None:
        write_inventory(
            self.tmp_path,
            """
services:
  hub:
    public_host: hub.test
    source: docker
    image: ghcr.io/org/hub
    ref: main
""",
        )
        apps = load_registry(self.tmp_path)
        assert apps[0].source == "docker"
        assert apps[0].image_ref() == "ghcr.io/org/hub:main"
        assert apps[0].compose_pin_image == "ghcr.io/org/hub:main"

    def test_image_ref_requires_image_and_tag(self) -> None:
        app = make_app("x", source="local")
        with pytest.raises(ValueError, match="no image"):
            app.image_ref()
        docker_app = make_app("hub", source="docker", image="ghcr.io/org/hub", ref="main")
        with pytest.raises(ValueError, match="empty image tag"):
            docker_app.image_ref("  ")

    def test_rejects_docker_without_image(self) -> None:
        write_inventory(
            self.tmp_path,
            """
services:
  hub:
    public_host: hub.test
    source: docker
""",
        )
        with pytest.raises(ValueError, match="image is required"):
            load_registry(self.tmp_path)

    def test_rejects_docker_image_with_tag(self) -> None:
        write_inventory(
            self.tmp_path,
            """
services:
  hub:
    public_host: hub.test
    source: docker
    image: "ghcr.io/org/hub:main"
""",
        )
        with pytest.raises(ValueError, match="without a tag"):
            load_registry(self.tmp_path)

    def test_requires_public_host_for_http(self) -> None:
        dest = self.tmp_path / "state" / "apps" / "x.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: x\nspec:\n"
            "  source: local\n"
            "  ports:\n    - name: http\n      containerPort: 80\n      expose: http\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="publicHost is required"):
            load_registry(self.tmp_path)

    def test_empty_registry(self) -> None:
        assert load_registry(self.tmp_path) == ()

    def test_registry_dir_missing(self) -> None:
        bare = self.tmp_path / "bare"
        bare.mkdir()
        assert load_registry(bare) == ()

    def test_default_path_and_blank_ref(self) -> None:
        write_inventory(
            self.tmp_path,
            """
services:
  app:
    public_host: app.test
    source: local
    ref: "   "
""",
        )
        apps = load_registry(self.tmp_path)
        assert apps[0].path == "apps/app"
        assert apps[0].ref == "main"

    def test_rejects_non_mapping(self) -> None:
        dest = self.tmp_path / "state" / "apps" / "app.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("- not a mapping\n", encoding="utf-8")
        with pytest.raises(ValueError, match="mapping"):
            load_registry(self.tmp_path)


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
        assert self.stack.core_services == ("gate", "router", "app")
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
        with pytest.raises(FileNotFoundError, match="package templates"):
            find_package_root(nested)


class TestApp(RaftTestCase):
    def test_abs_path(self) -> None:
        app = make_app("d", public_host="d.example.com", path="apps/d")
        (self.tmp_path / "apps" / "d").mkdir(parents=True)
        assert app.abs_path(self.tmp_path) == (self.tmp_path / "apps" / "d").resolve()
