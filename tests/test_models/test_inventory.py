"""Inventory loading and Stack helpers."""

from pathlib import Path

import pytest

from ..base import RaftTestCase, make_app, write_inventory
from raft.models import find_repo_root, load_inventory, load_stack


class TestLoadInventory(RaftTestCase):
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
        apps = load_inventory(self.tmp_path)
        assert len(apps) == 2
        assert apps[0].name == "app"
        assert apps[0].source == "local"
        assert apps[0].repo is None
        assert apps[0].path == "apps/app"
        assert apps[1].source == "git"
        assert apps[1].repo == "git@example.com:org/other.git"
        assert apps[1].ref == "develop"

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
            load_inventory(self.tmp_path)

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
            load_inventory(self.tmp_path)

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
        apps = load_inventory(self.tmp_path)
        assert len(apps) == 1
        assert apps[0].source == "docker"
        assert apps[0].image == "ghcr.io/org/hub"
        assert apps[0].repo is None
        assert apps[0].image_ref() == "ghcr.io/org/hub:main"
        assert apps[0].image_ref("sha256:abc") == "ghcr.io/org/hub@sha256:abc"
        assert apps[0].compose_pin_image == "ghcr.io/org/hub:main"

    def test_image_ref_requires_image_and_tag(self) -> None:
        app = make_app("x", source="local")
        with pytest.raises(ValueError, match="no image"):
            app.image_ref()
        docker_app = make_app(
            "hub", source="docker", image="ghcr.io/org/hub", ref="main"
        )
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
            load_inventory(self.tmp_path)

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
            load_inventory(self.tmp_path)

    def test_requires_public_host(self) -> None:
        dest = self.tmp_path / "state" / "apps" / "x.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: x\nspec:\n  source: local\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="publicHost is required"):
            load_inventory(self.tmp_path)

    def test_empty_registry(self) -> None:
        assert load_inventory(self.tmp_path) == ()

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
        apps = load_inventory(self.tmp_path)
        assert apps[0].path == "apps/app"
        assert apps[0].ref == "main"

    def test_rejects_non_table_service(self) -> None:
        dest = self.tmp_path / "state" / "apps" / "app.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("- not a mapping\n", encoding="utf-8")
        with pytest.raises(ValueError, match="mapping"):
            load_inventory(self.tmp_path)

    def test_rejects_empty_services(self) -> None:
        assert load_inventory(self.tmp_path) == ()


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
        assert self.app.tmp_alias == "app_tmp"
        assert self.app.tmp_container == "raft-app_tmp"
        assert (
            self.stack.upstream_file(self.app)
            == self.tmp_path / ".generated" / "nginx" / "upstreams" / "app.conf"
        )
        assert self.stack.certs_dir == self.tmp_path / "certs"
        assert self.stack.cert_files(self.app) == (
            self.tmp_path / "certs" / "app" / "origin.pem",
            self.tmp_path / "certs" / "app" / "origin.key",
        )
        assert self.stack.core_services == ("gate", "router", "app")
        with pytest.raises(KeyError, match="unknown app"):
            self.stack.app("nope")

    def test_image_and_ref_state_files(self) -> None:
        assert (
            self.stack.image_state_file(self.app)
            == self.tmp_path / ".deploy" / "app.image"
        )
        assert (
            self.stack.ref_state_file(self.app)
            == self.tmp_path / ".deploy" / "app.ref"
        )

    def test_load_stack_uses_find_when_root_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(self.tmp_path)
        stack = load_stack(None)
        assert stack.root == self.tmp_path.resolve()
        assert stack.app("app").name == "app"


class TestFindRepoRoot(RaftTestCase):
    def test_walks_up(self) -> None:
        write_inventory(
            self.tmp_path,
            """
services:
  app:
    public_host: app.test
    source: local
""",
        )
        nested = self.tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        assert find_repo_root(nested) == self.tmp_path.resolve()

    def test_via_package_parents(self) -> None:
        root = find_repo_root(self.tmp_path)
        assert (root / "compose.yaml").is_file()
        assert (root / "raft.yaml").is_file()

    def test_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        nested = self.tmp_path / "empty"
        nested.mkdir()
        real_is_file = Path.is_file

        def no_marker(self_path: Path) -> bool:
            if self_path.name in {"compose.yaml", "raft.yaml"}:
                return False
            return real_is_file(self_path)

        monkeypatch.setattr(Path, "is_file", no_marker)
        with pytest.raises(FileNotFoundError, match="orchestrator root"):
            find_repo_root(nested)


class TestApp(RaftTestCase):
    def test_abs_path(self) -> None:
        app = make_app("d", public_host="d.com", path="apps/d")
        (self.tmp_path / "apps" / "d").mkdir(parents=True)
        assert app.abs_path(self.tmp_path) == (self.tmp_path / "apps" / "d").resolve()
