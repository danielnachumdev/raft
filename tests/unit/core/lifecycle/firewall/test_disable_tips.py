"""Firewall tips gated by disable_tips on the document."""

from pathlib import Path

import yaml

from raft.core.lifecycle.firewall.recommendations import FirewallRecommendations
from tests.unit.base import RaftTestCase


class TestFirewallDisableTips(RaftTestCase):
    def test_disable_tips_hides_recommendations(self) -> None:
        home = Path(self.tmp_path)
        path = home / "host" / "firewall.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump({"version": 1, "disableTips": True, "rules": []}),
            encoding="utf-8",
        )
        body = FirewallRecommendations(home).list_public()
        assert body["recommendations"] == []
