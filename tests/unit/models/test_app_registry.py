"""AppRegistry load isolation and skip-bad-manifest behavior."""

import pytest

from raft.models.registry import AppRegistry
from raft.models.stack import load_stack

from ..base import RaftTestCase, make_app, write_inventory

LOCAL_GIT_INVENTORY = """
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
"""


class TestLoadRegistry(RaftTestCase):
    def test_local_and_git(self) -> None:
        write_inventory(self.tmp_path, LOCAL_GIT_INVENTORY)
        apps = AppRegistry(self.tmp_path).load()
        assert len(apps) == 2
        assert apps[0].name == "app" and apps[0].source == "local"
        assert apps[1].source == "git"
        assert apps[1].repo == "git@example.com:org/other.git"

    def test_skips_git_without_repo(self) -> None:
        write_inventory(
            self.tmp_path,
            """
services:
  broken:
    public_host: broken.test
    source: git
""",
        )
        result = AppRegistry(self.tmp_path).load_result()
        assert result.apps == ()
        assert any("repo is required" in i.error for i in result.issues)

    def test_skips_bad_source(self) -> None:
        write_inventory(
            self.tmp_path,
            """
services:
  x:
    public_host: x.test
    source: s3
""",
        )
        result = AppRegistry(self.tmp_path).load_result()
        assert result.apps == ()
        assert any("must be 'local', 'git', or 'docker'" in i.error for i in result.issues)

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
        apps = AppRegistry(self.tmp_path).load()
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

    def test_skips_docker_without_image(self) -> None:
        write_inventory(
            self.tmp_path,
            """
services:
  hub:
    public_host: hub.test
    source: docker
""",
        )
        result = AppRegistry(self.tmp_path).load_result()
        assert result.apps == ()
        assert any("image is required" in i.error for i in result.issues)

    def test_skips_docker_image_with_tag(self) -> None:
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
        result = AppRegistry(self.tmp_path).load_result()
        assert result.apps == ()
        assert any("without a tag" in i.error for i in result.issues)

    def test_skips_missing_public_host_for_http(self) -> None:
        dest = self.tmp_path / "state" / "apps" / "x.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: x\nspec:\n"
            "  source: local\n"
            "  ports:\n    - name: http\n      containerPort: 80\n      expose: http\n",
            encoding="utf-8",
        )
        result = AppRegistry(self.tmp_path).load_result()
        assert result.apps == ()
        assert any("publicHost is required" in i.error for i in result.issues)

    def test_isolates_bad_yaml_from_good_apps(self) -> None:
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
        bad = self.tmp_path / "state" / "apps" / "broken.yaml"
        bad.write_text("not: [valid\n", encoding="utf-8")
        result = AppRegistry(self.tmp_path).load_result()
        assert [a.name for a in result.apps] == ["app"]
        assert any(i.file == "broken.yaml" for i in result.issues)
        stack = load_stack(self.tmp_path)
        assert stack.app("app").name == "app"
        assert stack.registry_issues and stack.registry_issues[0].file == "broken.yaml"

    def test_empty_registry(self) -> None:
        assert AppRegistry(self.tmp_path).load() == ()

    def test_registry_dir_missing(self) -> None:
        bare = self.tmp_path / "bare"
        bare.mkdir()
        assert AppRegistry(bare).load() == ()

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
        apps = AppRegistry(self.tmp_path).load()
        assert apps[0].path == "apps/app"
        assert apps[0].ref == "main"

    def test_skips_non_mapping(self) -> None:
        dest = self.tmp_path / "state" / "apps" / "app.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("- not a mapping\n", encoding="utf-8")
        result = AppRegistry(self.tmp_path).load_result()
        assert result.apps == ()
        assert any("mapping" in i.error for i in result.issues)

    def test_write_skips_corrupt_host_peer(self) -> None:
        apps = self.tmp_path / "state" / "apps"
        apps.mkdir(parents=True, exist_ok=True)
        (apps / "junk.yaml").write_text("- not a mapping\n", encoding="utf-8")
        path = AppRegistry(self.tmp_path).write(
            {
                "apiVersion": "raft/v1",
                "kind": "App",
                "metadata": {"name": "ok"},
                "spec": {
                    "publicHost": "ok.test",
                    "source": "local",
                    "path": "apps/ok",
                    "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
                },
            }
        )
        assert path.name == "ok.yaml"
