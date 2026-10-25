"""Shared recommendation dismissal store."""

from pathlib import Path
from unittest.mock import patch

from raft.core.core.models.state.recommendation_dismissals import (
    ALERTS_STATE_DIR,
    FIREWALL_STATE_DIR,
    AlertDismissalStore,
    FirewallDismissalStore,
    RecommendationDismissalStore,
)
from tests.unit.base import RaftTestCase


class TestRecommendationDismissalStore(RaftTestCase):
    def test_firewall_and_alerts_paths(self) -> None:
        home = Path(self.tmp_path)
        fw = FirewallDismissalStore(home)
        al = AlertDismissalStore(home)
        assert fw.root == home / FIREWALL_STATE_DIR
        assert al.root == home / ALERTS_STATE_DIR
        fw.dismiss("permit-port-80")
        al.dismiss("any-service-oom")
        assert fw.list_ids() == {"permit-port-80"}
        assert al.list_ids() == {"any-service-oom"}
        assert fw.path != al.path

    def test_corrupt_and_blank(self) -> None:
        store = RecommendationDismissalStore(Path(self.tmp_path), "host/misc")
        store.path.parent.mkdir(parents=True, exist_ok=True)
        store.path.write_text("[1,2,3]\n", encoding="utf-8")
        assert store.list_ids() == frozenset()
        store.path.write_text('{"dismissed": "x"}\n', encoding="utf-8")
        assert store.list_ids() == frozenset()
        store.path.write_text("{bad", encoding="utf-8")
        assert store.list_ids() == frozenset()
        assert store.dismiss("  ") == frozenset()
        with patch("os.replace", side_effect=OSError("boom")):
            try:
                store.dismiss("x")
            except OSError:
                pass
        assert list(store.root.glob("*.tmp")) == []
