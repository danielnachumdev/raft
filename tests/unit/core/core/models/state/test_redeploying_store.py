"""RedeployingStore marker under services/<app>/deploy/redeploying."""

from pathlib import Path

from raft.core.core.models.state.redeploying_store import RedeployingStore

from tests.unit.base import RaftTestCase


class TestRedeployingStore(RaftTestCase):
    def test_mark_clear_and_container_path(self) -> None:
        root = Path(self.tmp_path)
        store = RedeployingStore(root)
        assert not store.is_redeploying("demo-api")
        store.mark("demo-api")
        assert store.is_redeploying("demo-api")
        path = root / "services" / "demo-api" / "deploy" / "redeploying"
        assert path.is_file()
        assert "demo-api" in RedeployingStore.container_marker("demo-api")
        assert path.name in RedeployingStore.container_marker("demo-api")
        store.clear("demo-api")
        assert not store.is_redeploying("demo-api")
        store.clear("demo-api")
