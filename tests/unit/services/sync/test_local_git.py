"""SourceSync local and git coverage."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from raft.services.sync import SourceSync

from ...base import git_call_args, make_app, make_stack
from .base import SyncTestCase


class TestSyncLocalGit(SyncTestCase):
    def test_sync_local_ok(self, caplog: pytest.LogCaptureFixture) -> None:
        (self.tmp_path / "apps" / "app").mkdir(parents=True)
        with caplog.at_level("INFO"):
            self.syncer.sync([self.app])
        self.shell.git.assert_not_called()
        assert any(self.app.path in r.getMessage() for r in caplog.records)

    def test_sync_local_missing_path(self) -> None:
        with pytest.raises(RuntimeError, match="local app path missing"):
            self.syncer.sync([self.app])

    def test_sync_git_clone_fetch_checkout(self) -> None:
        self.git_syncer(repo="git@example.com:org/svc.git")
        dest = self.app.abs_path(self.tmp_path)
        self.shell.git.side_effect = self._clone_fetch_git(dest, "abc123def456\n")
        self.syncer.sync([self.app], ref_override="deadbeef")
        cmds = [c[0] for c in git_call_args(self.shell)]
        assert "clone" in cmds and "fetch" in cmds and "checkout" in cmds
        state = (self.tmp_path / "deploy" / "svc.ref").read_text(encoding="utf-8")
        assert "abc123def456" in state and "deadbeef" in state

    def _clone_fetch_git(self, dest, rev: str):
        def git(*args, **kwargs):
            result = MagicMock(returncode=0, stdout="")
            if args and args[0] == "clone":
                dest.mkdir(parents=True)
                (dest / ".git").mkdir()
            elif args[:2] == ("status", "--porcelain"):
                result.stdout = ""
            elif args[:2] == ("rev-parse", "--verify"):
                result.stdout = rev
            return result

        return git

    def test_sync_git_refuses_dirty_without_force(self) -> None:
        self.git_syncer(repo="git@example.com:org/svc.git")
        self.ensure_git_checkout()

        def git(*args, **kwargs):
            result = MagicMock(returncode=0, stdout="")
            if args[:2] == ("status", "--porcelain"):
                result.stdout = " M file.txt\n"
            return result

        self.shell.git.side_effect = git
        with pytest.raises(RuntimeError, match="local changes"):
            self.syncer.sync([self.app])

    def test_sync_git_force_allows_dirty(self) -> None:
        self.git_syncer(repo="git@example.com:org/svc.git")
        self.ensure_git_checkout()

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
        self.git_syncer(repo="git@github.com:org/svc.git")
        auth = MagicMock()
        auth.effective_clone_url.return_value = "git@github.com-raft-svc:org/svc.git"
        self.syncer = SourceSync(self.stack, self.shell)
        self.syncer.auth = auth
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
        self.git_syncer(repo="git@example.com:org/svc.git")
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
        self.shell.git.side_effect = self._clone_fetch_git(dest, "abc123def456\n")
        self.shell.docker.return_value = MagicMock(
            returncode=0, stdout="sha256:deadbeef\n", stderr=""
        )
        self.syncer.sync([app])
        assert (self.tmp_path / "deploy" / "hub.ref").is_file()
        pulls = [c.args for c in self.shell.docker.call_args_list if c.args[:1] == ("pull",)]
        assert pulls

    def test_sync_git_falls_back_to_origin_ref(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.git_syncer(repo="git@example.com:org/svc.git")
        self.ensure_git_checkout()
        monkeypatch.setenv("VPS_SYNC_REF", "feature")
        self.shell.git.side_effect = self._origin_fallback_git()
        self.syncer.sync([self.app])
        checkout = [c for c in git_call_args(self.shell) if c and c[0] == "checkout"][0]
        assert "feedface0001" in checkout

    def _origin_fallback_git(self):
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

        return git

    def test_sync_git_unresolvable_ref(self) -> None:
        self.git_syncer(repo="git@example.com:org/svc.git", ref="nope")
        self.ensure_git_checkout()

        def git(*args, **kwargs):
            result = MagicMock(stdout="")
            result.returncode = 1 if args[:2] == ("rev-parse", "--verify") else 0
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
