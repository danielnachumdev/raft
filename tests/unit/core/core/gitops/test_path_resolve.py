"""GitOps flat path resolve."""

from pathlib import Path

from raft.core.core.gitops import GitopsDocKind
from raft.core.core.gitops.path_resolve import GitopsPathResolve
from tests.unit.base import RaftTestCase


class TestGitopsPathResolve(RaftTestCase):
    def test_flat_paths(self) -> None:
        home = Path(self.tmp_path)
        resolve = GitopsPathResolve(home)
        assert resolve.path(GitopsDocKind.SETTINGS) == home / "host" / "settings.yaml"
        assert resolve.path(GitopsDocKind.FIREWALL) == home / "host" / "firewall.yaml"
        assert resolve.path(GitopsDocKind.ALERTS) == home / "host" / "alerts.yaml"
        assert (
            resolve.path(GitopsDocKind.NOTIFICATIONS)
            == home / "host" / "notifications.yaml"
        )
        assert resolve.path(GitopsDocKind.RBAC) == home / "host" / "rbac.yaml"
