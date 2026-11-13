"""GithubDeployHostGit argv + dashboard routing."""

from unittest.mock import MagicMock

from raft.core.platform.github.deploy.host_git import GithubDeployHostGit
from tests.unit.base import RaftTestCase, StackMakers


class TestGithubDeployHostGit(RaftTestCase):
    def test_auth_and_apply_argv(self) -> None:
        assert GithubDeployHostGit._auth_argv(
            "docket", "git@github.com:demo/docket-deploy.git"
        ) == [
            "raft",
            "auth",
            "setup",
            "docket",
            "--repo",
            "git@github.com:demo/docket-deploy.git",
        ]
        assert GithubDeployHostGit._apply_argv(
            "git@github.com:demo/docket-deploy.git",
            ref="main",
            manifest_path=".raft/app.yaml",
        ) == [
            "raft",
            "apply",
            "--git",
            "git@github.com:demo/docket-deploy.git",
            "--ref",
            "main",
            "--manifest_path",
            ".raft/app.yaml",
        ]

    def test_prepare_key_runs_oneshot_then_reads_pubkey(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path)
        oneshot = MagicMock()
        gate = MagicMock()
        gate.in_dashboard.return_value = True
        host = GithubDeployHostGit(stack, oneshot=oneshot, gate=gate)
        ssh_dir = self.tmp_path / "ssh"
        keys = ssh_dir / "raft"
        keys.mkdir(parents=True)
        pub = keys / "docket_ed25519.pub"
        pub.write_text("ssh-ed25519 AAAA test\n", encoding="utf-8")
        auth = MagicMock()
        auth.show_pubkey.return_value = "ssh-ed25519 AAAA test"
        with self._patch_auth(auth):
            out = host.prepare_key("docket", "git@github.com:demo/docket.git")
        assert out == "ssh-ed25519 AAAA test"
        oneshot.run.assert_called_once()
        gate.ensure.assert_called()

    def test_apply_git_uses_docker_oneshot(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path)
        oneshot = MagicMock()
        gate = MagicMock()
        host = GithubDeployHostGit(stack, oneshot=oneshot, gate=gate)
        host.apply_git(
            "git@github.com:demo/docket.git",
            ref="abc",
            manifest_path=".raft/app.yaml",
        )
        args, kwargs = oneshot.run.call_args
        assert args[0][0:4] == ["raft", "apply", "--git", "git@github.com:demo/docket.git"]
        assert kwargs["with_docker"] is True

    @staticmethod
    def _patch_auth(auth: MagicMock):
        from unittest.mock import patch

        return patch(
            "raft.core.platform.github.deploy.host_git.GitAuthManager",
            return_value=auth,
        )
