"""AppSourceIdentity normalize + registry name-vs-source ownership."""

import pytest
import yaml

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.app import App
from raft.core.core.models.registry import AppRegistry
from raft.core.core.models.source_identity import AppSourceIdentity

from tests.unit.base import AppMakers, AppliedInventory, RaftTestCase
from tests.unit.cta_asserts import CtaAsserts


class TestAppSourceIdentity(RaftTestCase):
    def test_git_ssh_https_same_remote(self) -> None:
        ssh = AppSourceIdentity.from_app(
            AppMakers.make_git_app(repo="git@github.com:demo-org/demo-api.git")
        )
        https = AppSourceIdentity.from_app(
            AppMakers.make_git_app(repo="https://github.com/demo-org/demo-api")
        )
        assert ssh == https
        assert ssh.key == "github.com/demo-org/demo-api"

    def test_git_ref_not_in_identity(self) -> None:
        a = AppSourceIdentity.from_app(AppMakers.make_git_app(ref="main"))
        b = AppSourceIdentity.from_app(AppMakers.make_git_app(ref="abc123"))
        assert a == b

    def test_local_path_normalized(self) -> None:
        a = AppSourceIdentity.from_app(
            AppMakers.make_app(path="apps/demo-api/nested/../")
        )
        b = AppSourceIdentity.from_app(AppMakers.make_app(path="apps/demo-api"))
        assert a == b
        assert a.label() == "local path=apps/demo-api"
        assert AppSourceIdentity._normalize_local_path("../apps/x") == "apps/x"
        assert AppSourceIdentity._normalize_local_path("..") == "."
        assert AppSourceIdentity._normalize_local_path("a/../../b") == "b"
        assert AppSourceIdentity._normalize_local_path("  ") == "."

    def test_git_empty_repo_key(self) -> None:
        assert AppSourceIdentity._normalize_git_repo("  ") == ""
        assert AppSourceIdentity._normalize_git_repo(
            "ssh://git@github.com/demo-org/demo-api.git"
        ) == "github.com/demo-org/demo-api"

    def test_docker_image_ignores_ref(self) -> None:
        a = AppSourceIdentity.from_app(
            AppMakers.make_app(
                source="docker", image="ghcr.io/Demo-Org/demo-api", ref="v1"
            )
        )
        b = AppSourceIdentity.from_app(
            AppMakers.make_app(
                source="docker", image="ghcr.io/demo-org/demo-api", ref="v2"
            )
        )
        assert a == b
        assert a.label() == "docker image=ghcr.io/demo-org/demo-api"

    def test_local_vs_git_differ(self) -> None:
        local = AppSourceIdentity.from_app(AppMakers.make_app(name="demo-api"))
        git = AppSourceIdentity.from_app(
            AppMakers.make_git_app(
                "demo-api", repo="git@github.com:demo-org/demo-api.git"
            )
        )
        assert local != git


class TestRegistrySourceOwnership(RaftTestCase):
    def test_same_source_allows_update(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "demo-api",
            source="git",
            repo="git@github.com:demo-org/demo-api.git",
            public_host="demo-api.test",
        )
        path = AppRegistry(self.tmp_path).write(
            self._git_doc("demo-api", "https://github.com/demo-org/demo-api.git", "v2")
        )
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["spec"]["ref"] == "v2"

    def test_different_git_repo_denied(self) -> None:
        self._seed_git("demo-api", "git@github.com:demo-org/demo-api.git")
        with CtaAsserts.raises(
            match="different source",
            contains=(
                "demo-org/demo-api",
                "other-org/other-api",
                "raft delete demo-api",
            ),
        ):
            AppRegistry(self.tmp_path).write(
                self._git_doc("demo-api", "git@github.com:other-org/other-api.git", "main")
            )

    def _seed_git(self, name: str, repo: str) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path, name, source="git", repo=repo, public_host=f"{name}.test"
        )

    def test_local_vs_git_denied(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", source="local", path="apps/demo-api"
        )
        with pytest.raises(OperatorError, match="different source") as caught:
            AppRegistry(self.tmp_path).write(
                self._git_doc(
                    "demo-api",
                    "git@github.com:demo-org/demo-api.git",
                    "main",
                )
            )
        CtaAsserts.operator(
            caught.value,
            contains=("local path=apps/demo-api", "git repo=", "Fix:"),
        )

    def test_docker_vs_docker_different_image_denied(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "demo-api",
            source="docker",
            image="ghcr.io/demo-org/demo-api",
            public_host="demo-api.test",
            build_context=None,
        )
        with pytest.raises(OperatorError, match="different source"):
            AppRegistry(self.tmp_path).write(
                self._docker_doc("demo-api", "ghcr.io/other-org/other-api")
            )

    def test_delete_then_reapply_allows(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "demo-api",
            source="git",
            repo="git@github.com:demo-org/demo-api.git",
        )
        assert AppRegistry(self.tmp_path).delete("demo-api")
        path = AppRegistry(self.tmp_path).write(
            self._git_doc(
                "demo-api",
                "git@github.com:other-org/other-api.git",
                "main",
            )
        )
        assert path.is_file()

    def test_corrupt_existing_allows_overwrite(self) -> None:
        dest = self.tmp_path / "state" / "apps" / "demo-api.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("- not a mapping\n", encoding="utf-8")
        path = AppRegistry(self.tmp_path).write(
            self._local_doc("demo-api", "apps/demo-api")
        )
        assert path.is_file()

    @staticmethod
    def _git_doc(name: str, repo: str, ref: str) -> dict:
        return {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": name},
            "spec": {
                "publicHost": f"{name}.test",
                "source": "git",
                "repo": repo,
                "ref": ref,
                "path": f"apps/{name}",
                "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
            },
        }

    @staticmethod
    def _docker_doc(name: str, image: str) -> dict:
        return {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": name},
            "spec": {
                "publicHost": f"{name}.test",
                "source": "docker",
                "image": image,
                "ref": "main",
                "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
            },
        }

    @staticmethod
    def _local_doc(name: str, path: str) -> dict:
        return {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": name},
            "spec": {
                "publicHost": f"{name}.test",
                "source": "local",
                "path": path,
                "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
            },
        }


class TestRejectTakeover(RaftTestCase):
    def test_same_identity_noop(self) -> None:
        app = AppMakers.make_git_app("demo-api", repo="git@github.com:demo-org/demo-api.git")
        AppSourceIdentity.reject_takeover(app, app)

    def test_mismatch_raises(self) -> None:
        existing = AppMakers.make_app("demo-api", source="local", path="apps/demo-api")
        incoming = App(
            name="demo-api",
            public_host="demo-api.test",
            source="docker",
            path="apps/demo-api",
            image="ghcr.io/demo-org/demo-api",
        )
        with pytest.raises(OperatorError, match="different source"):
            AppSourceIdentity.reject_takeover(existing, incoming)
