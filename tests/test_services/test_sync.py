"""SourceSync local/git behavior (git/shell mocked)."""

from unittest.mock import MagicMock

import pytest

from ..base import git_call_args, make_app, make_git_app, make_stack
from .base import ServicesTestCase
from raft.services import SourceSync


class TestSourceSync(ServicesTestCase):
    @pytest.fixture(autouse=True)
    def _sync_setup(self, _services_setup) -> None:
        self.syncer = SourceSync(self.stack, self.shell)

    def _git_syncer(self, **app_kwargs) -> SourceSync:
        app = make_git_app(**app_kwargs)
        self.stack = make_stack(self.tmp_path, (app,))
        self.app = app
        self.syncer = SourceSync(self.stack, self.shell)
        return self.syncer

    def _ensure_git_checkout(self) -> None:
        dest = self.app.abs_path(self.tmp_path)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / ".git").mkdir(exist_ok=True)

    def test_sync_local_ok(self, caplog: pytest.LogCaptureFixture) -> None:
        (self.tmp_path / "apps" / "app").mkdir(parents=True)
        with caplog.at_level("INFO"):
            self.syncer.sync([self.app])
        self.shell.git.assert_not_called()
        assert "local (apps/app)" in caplog.text

    def test_sync_local_missing_path(self) -> None:
        with pytest.raises(RuntimeError, match="local app path missing"):
            self.syncer.sync([self.app])

    def test_sync_git_clone_fetch_checkout(self) -> None:
        self._git_syncer(repo="git@example.com:org/svc.git")
        dest = self.app.abs_path(self.tmp_path)

        def git(*args, **kwargs):
            result = MagicMock(returncode=0, stdout="")
            if args and args[0] == "clone":
                dest.mkdir(parents=True)
                (dest / ".git").mkdir()
            elif args[:2] == ("status", "--porcelain"):
                result.stdout = ""
            elif args[:2] == ("rev-parse", "--verify"):
                result.stdout = "abc123def456\n"
            return result

        self.shell.git.side_effect = git
        self.syncer.sync([self.app], ref_override="deadbeef")

        cmds = [c[0] for c in git_call_args(self.shell)]
        assert "clone" in cmds
        assert "fetch" in cmds
        assert "checkout" in cmds
        state = (self.tmp_path / "deploy" / "svc.ref").read_text(encoding="utf-8")
        assert "abc123def456" in state
        assert "deadbeef" in state

    def test_sync_git_refuses_dirty_without_force(self) -> None:
        self._git_syncer(repo="git@example.com:org/svc.git")
        self._ensure_git_checkout()

        def git(*args, **kwargs):
            result = MagicMock(returncode=0, stdout="")
            if args[:2] == ("status", "--porcelain"):
                result.stdout = " M file.txt\n"
            return result

        self.shell.git.side_effect = git
        with pytest.raises(RuntimeError, match="local changes"):
            self.syncer.sync([self.app])

    def test_sync_git_force_allows_dirty(self) -> None:
        self._git_syncer(repo="git@example.com:org/svc.git")
        self._ensure_git_checkout()

        def git(*args, **kwargs):
            result = MagicMock(returncode=0, stdout="")
            if args[:2] == ("status", "--porcelain"):
                result.stdout = " M file.txt\n"
            elif args[:2] == ("rev-parse", "--verify"):
                result.stdout = "aaa111bbb222\n"
            return result

        self.shell.git.side_effect = git
        self.syncer.sync([self.app], force=True)
        assert any(c[0] == "checkout" for c in git_call_args(self.shell))
        assert any(c[:2] == ("remote", "set-url") for c in git_call_args(self.shell))

    def test_sync_uses_auth_clone_url(self) -> None:
        self._git_syncer(repo="git@github.com:org/svc.git")
        auth = MagicMock()
        auth.effective_clone_url.return_value = "git@github.com-raft-svc:org/svc.git"
        self.syncer = SourceSync(self.stack, self.shell, auth=auth)
        dest = self.app.abs_path(self.tmp_path)

        def git(*args, **kwargs):
            result = MagicMock(returncode=0, stdout="")
            if args and args[0] == "clone":
                assert args[2] == "git@github.com-raft-svc:org/svc.git"
                dest.mkdir(parents=True)
                (dest / ".git").mkdir()
            elif args[:2] == ("rev-parse", "--verify"):
                result.stdout = "abc123def456\n"
            return result

        self.shell.git.side_effect = git
        self.syncer.sync([self.app])

    def test_sync_git_nonempty_non_git_dir(self) -> None:
        self._git_syncer(repo="git@example.com:org/svc.git")
        dest = self.app.abs_path(self.tmp_path)
        dest.mkdir(parents=True)
        (dest / "README").write_text("x", encoding="utf-8")
        with pytest.raises(RuntimeError, match="not a git checkout"):
            self.syncer.sync([self.app])

    def test_sync_replaces_contract_stub_then_docker_pull(self) -> None:
        app = make_app(
            "hub",
            source="docker",
            image="ghcr.io/org/hub",
            ref="main",
            repo="git@example.com:org/hub.git",
            path="apps/hub",
        )
        self.stack = make_stack(self.tmp_path, (app,))
        self.app = app
        self.syncer = SourceSync(self.stack, self.shell)
        dest = app.abs_path(self.tmp_path)
        (dest / ".raft").mkdir(parents=True)
        (dest / ".raft" / "app.yaml").write_text("x", encoding="utf-8")

        def git(*args, **kwargs):
            result = MagicMock(returncode=0, stdout="")
            if args and args[0] == "clone":
                dest.mkdir(parents=True)
                (dest / ".git").mkdir()
            elif args[:2] == ("status", "--porcelain"):
                result.stdout = ""
            elif args[:2] == ("rev-parse", "--verify"):
                result.stdout = "abc123def456\n"
            return result

        self.shell.git.side_effect = git
        self.shell.docker.return_value = MagicMock(
            returncode=0, stdout="sha256:deadbeef\n", stderr=""
        )
        self.syncer.sync([app])
        assert (self.tmp_path / "deploy" / "hub.ref").is_file()
        pulls = [c.args for c in self.shell.docker.call_args_list if c.args[:1] == ("pull",)]
        assert pulls

    def test_sync_git_falls_back_to_origin_ref(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._git_syncer(repo="git@example.com:org/svc.git")
        self._ensure_git_checkout()
        monkeypatch.setenv("VPS_SYNC_REF", "feature")

        def git(*args, **kwargs):
            result = MagicMock(returncode=0, stdout="")
            if args[:2] == ("status", "--porcelain"):
                result.stdout = ""
            elif args[:2] == ("rev-parse", "--verify"):
                wanted = args[2]
                if wanted == "feature":
                    result.returncode = 1
                elif wanted == "origin/feature":
                    result.stdout = "feedface0001\n"
                else:
                    result.returncode = 1
            return result

        self.shell.git.side_effect = git
        self.syncer.sync([self.app])
        checkout = [c for c in git_call_args(self.shell) if c and c[0] == "checkout"][0]
        assert "feedface0001" in checkout

    def test_sync_git_unresolvable_ref(self) -> None:
        self._git_syncer(repo="git@example.com:org/svc.git", ref="nope")
        self._ensure_git_checkout()

        def git(*args, **kwargs):
            result = MagicMock(stdout="")
            if args[:2] == ("rev-parse", "--verify"):
                result.returncode = 1
            else:
                result.returncode = 0
            return result

        self.shell.git.side_effect = git
        with pytest.raises(RuntimeError, match="cannot resolve ref"):
            self.syncer.sync([self.app])

    def test_sync_defaults_to_all_stack_apps(self) -> None:
        (self.tmp_path / "apps" / "a").mkdir(parents=True)
        (self.tmp_path / "apps" / "b").mkdir(parents=True)
        apps = (
            make_app("a", public_host="a.test", path="apps/a"),
            make_app("b", public_host="b.test", path="apps/b"),
        )
        SourceSync(make_stack(self.tmp_path, apps), MagicMock()).sync()

    def test_sync_docker_pull_and_pin(self) -> None:
        app = make_app(
            "hub",
            source="docker",
            image="ghcr.io/org/hub",
            ref="main",
            public_host="hub.test",
        )
        self.stack = make_stack(self.tmp_path, (app,))
        self.syncer = SourceSync(self.stack, self.shell)

        def docker(*args, **kwargs):
            result = MagicMock(returncode=0, stdout="")
            if args[:2] == ("image", "inspect"):
                result.stdout = "ghcr.io/org/hub@sha256:deadbeef\n"
            return result

        self.shell.docker.side_effect = docker
        self.syncer.sync([app], ref_override="abc123")
        self.shell.docker.assert_any_call("pull", "ghcr.io/org/hub:abc123")
        self.shell.docker.assert_any_call(
            "tag", "ghcr.io/org/hub:abc123", "ghcr.io/org/hub:main"
        )
        state = (self.tmp_path / "deploy" / "hub.ref").read_text(encoding="utf-8")
        assert "abc123" in state
        assert "ghcr.io/org/hub@sha256:deadbeef" in state

    def test_sync_docker_pin_equals_pull(self) -> None:
        app = make_app(
            "hub",
            source="docker",
            image="ghcr.io/org/hub",
            ref="main",
            public_host="hub.test",
        )
        self.stack = make_stack(self.tmp_path, (app,))
        self.syncer = SourceSync(self.stack, self.shell)

        def docker(*args, **kwargs):
            result = MagicMock(returncode=0, stdout="")
            if args[:2] == ("image", "inspect"):
                result.stdout = "sha256:abc\n"
            return result

        self.shell.docker.side_effect = docker
        self.syncer.sync([app])
        self.shell.docker.assert_any_call("pull", "ghcr.io/org/hub:main")
        assert not any(c.args[:1] == ("tag",) for c in self.shell.docker.call_args_list)
