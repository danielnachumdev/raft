"""SourceSync docker pull/pin coverage."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from raft.services import SourceSync

from ...base import make_app, make_stack
from .base import SyncTestCase


class TestSyncDocker(SyncTestCase):
    def test_sync_docker_pull_and_pin(self) -> None:
        self._test_sync_docker_pull_and_pin_p1()
        self._test_sync_docker_pull_and_pin_p2()

    def _test_sync_docker_pull_and_pin_p1(self) -> None:
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

    def _test_sync_docker_pull_and_pin_p2(self) -> None:
        self.shell.docker.assert_any_call(
            "pull", "ghcr.io/org/hub:abc123", capture=True, check=False
        )
        self.shell.docker.assert_any_call("tag", "ghcr.io/org/hub:abc123", "ghcr.io/org/hub:main")
        state = (self.tmp_path / "deploy" / "hub.ref").read_text(encoding="utf-8")
        assert "abc123" in state
        assert "ghcr.io/org/hub@sha256:deadbeef" in state

    def test_sync_docker_pin_equals_pull(self) -> None:
        self._test_sync_docker_pin_equals_pull_p1()
        self._test_sync_docker_pin_equals_pull_p2()

    def _test_sync_docker_pin_equals_pull_p1(self) -> None:
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

    def _test_sync_docker_pin_equals_pull_p2(self) -> None:
        self.shell.docker.assert_any_call(
            "pull", "ghcr.io/org/hub:main", capture=True, check=False
        )
        assert not any(c.args[:1] == ("tag",) for c in self.shell.docker.call_args_list)

    def test_sync_docker_unauthorized_clear_fix(self) -> None:
        app = make_app(
            "hub",
            source="docker",
            image="ghcr.io/org/hub",
            ref="main",
            public_host="hub.test",
        )
        self.stack = make_stack(self.tmp_path, (app,))
        self.syncer = SourceSync(self.stack, self.shell)
        self.shell.docker.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error response from daemon: unauthorized\nunauthorized\n",
        )
        with pytest.raises(RuntimeError, match="docker login ghcr.io") as exc:
            self.syncer.sync([app])
        msg = str(exc.value)
        assert "cannot pull ghcr.io/org/hub:main" in msg
        assert "raft auth" in msg.lower()
        assert "command failed" not in msg.lower()

    def test_sync_docker_pull_other_error_reraises(self) -> None:
        app = make_app(
            "hub",
            source="docker",
            image="ghcr.io/org/hub",
            ref="main",
            public_host="hub.test",
        )
        self.stack = make_stack(self.tmp_path, (app,))
        self.syncer = SourceSync(self.stack, self.shell)
        self.shell.docker.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="dial tcp: lookup ghcr.io: no such host\n",
        )
        with pytest.raises(RuntimeError, match="docker pull failed") as exc:
            self.syncer.sync([app])
        assert "no such host" in str(exc.value)

    def test_sync_git_clone_fetch_checkout_failures(self) -> None:
        self._test_sync_git_clone_fetch_checkout_failures_p1()
        self._test_sync_git_clone_fetch_checkout_failures_p2()
        self._test_sync_git_clone_fetch_checkout_failures_p3()

    def _test_sync_git_clone_fetch_checkout_failures_p1(self) -> None:
        self.git_syncer(repo="git@example.com:org/svc.git")
        self.shell.git.side_effect = RuntimeError("Permission denied (publickey)")
        with pytest.raises(RuntimeError, match="git auth failed"):
            self.syncer.sync([self.app])

        self.ensure_git_checkout()
        calls = {"n": 0}

        def git(*args, **kwargs):
            calls["n"] += 1
            if args[:1] == ("remote",):
                raise RuntimeError("Could not resolve host: example.com")
            return MagicMock(returncode=0, stdout="")

        self.shell.git.side_effect = git
        with pytest.raises(RuntimeError, match="cannot reach"):
            self.syncer.sync([self.app])

    def _test_sync_git_clone_fetch_checkout_failures_p2(self) -> None:
        def git_fetch(*args, **kwargs):
            if args[:1] == ("fetch",):
                raise RuntimeError("network unreachable")
            if args[:2] == ("status", "--porcelain"):
                return MagicMock(returncode=0, stdout="")
            if args[:1] == ("remote",):
                return MagicMock(returncode=0, stdout="")
            return MagicMock(returncode=0, stdout="")

        self.shell.git.side_effect = git_fetch
        with pytest.raises(RuntimeError, match="cannot reach"):
            self.syncer.sync([self.app])

    def _test_sync_git_clone_fetch_checkout_failures_p3(self) -> None:
        def git_checkout(*args, **kwargs):
            if args[:1] == ("checkout",):
                raise RuntimeError("pathspec did not match")
            if args[:2] == ("status", "--porcelain"):
                return MagicMock(returncode=0, stdout="")
            if args[:2] == ("rev-parse", "--verify"):
                return MagicMock(returncode=0, stdout="abc123\n")
            return MagicMock(returncode=0, stdout="")

        self.shell.git.side_effect = git_checkout
        with pytest.raises(RuntimeError, match="git command failed"):
            self.syncer.sync([self.app])
