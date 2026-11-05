"""TemporaryOverrideWarn copy for GitOps mutators."""

from raft.core.core.gitops import GitopsDocKind, TemporaryOverrideWarn

from tests.unit.base import RaftTestCase


class TestTemporaryOverrideWarn(RaftTestCase):
    def test_host_path_and_write_warning(self) -> None:
        assert TemporaryOverrideWarn.host_path(GitopsDocKind.FIREWALL) == (
            "host/firewall.yaml"
        )
        msg = TemporaryOverrideWarn.after_write(GitopsDocKind.ALERTS)
        assert msg.startswith("warning:")
        assert "host/alerts.yaml" in msg
        assert "Sync host config" in msg
        assert "temporary" in msg.lower()

    def test_tips_dismiss_warning(self) -> None:
        msg = TemporaryOverrideWarn.after_tips_dismiss(GitopsDocKind.FIREWALL)
        assert msg.startswith("warning:")
        assert "disable_tips: true" in msg
        assert "host/firewall.yaml" in msg
