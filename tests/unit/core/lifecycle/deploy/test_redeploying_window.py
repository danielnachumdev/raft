"""RedeployingWindow sets and clears the cutover marker."""

from pathlib import Path

from raft.core.core.models.state.redeploying_store import RedeployingStore
from raft.core.lifecycle.deploy.redeploying_window import RedeployingWindow

from tests.unit.base import RaftTestCase


class TestRedeployingWindow(RaftTestCase):
    def test_clears_on_success_and_failure(self) -> None:
        root = Path(self.tmp_path)
        store = RedeployingStore(root)
        with RedeployingWindow(root, "demo-api"):
            assert store.is_redeploying("demo-api")
        assert not store.is_redeploying("demo-api")
        try:
            with RedeployingWindow(root, "demo-api"):
                assert store.is_redeploying("demo-api")
                raise RuntimeError("cutover boom")
        except RuntimeError:
            pass
        assert not store.is_redeploying("demo-api")
