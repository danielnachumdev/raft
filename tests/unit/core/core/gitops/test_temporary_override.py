"""GitOps temporary-override copy story for live host mutators (#318)."""

from raft.core.core.gitops import GitopsDocKind, TemporaryOverrideWarn

from tests.unit.base import RaftTestCase


class TestTemporaryOverrideWarnStory(RaftTestCase):
    """Operator Saves on the host; Sync will replace the flat YAML path.

    Scenario:
      1) after_write names the host/<kind>.yaml path and Sync wipe.
      2) tip dismiss points at durable disable_tips in the GitOps repo.
    """

    def test_write_warning_names_host_path_and_sync(self) -> None:
        assert TemporaryOverrideWarn.host_path(GitopsDocKind.FIREWALL) == (
            "host/firewall.yaml"
        )
        msg = TemporaryOverrideWarn.after_write(GitopsDocKind.ALERTS)
        assert msg.startswith("warning:")
        assert "host/alerts.yaml" in msg
        assert "GitOps Sync" in msg
        assert "temporary" in msg.lower()

    def test_tips_dismiss_points_at_disable_tips_in_repo(self) -> None:
        msg = TemporaryOverrideWarn.after_tips_dismiss(GitopsDocKind.FIREWALL)
        assert msg.startswith("warning:")
        assert "disable_tips: true" in msg
        assert "host/firewall.yaml" in msg
