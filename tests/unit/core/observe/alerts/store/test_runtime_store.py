"""AlertRuntimeStore load/save."""
from pathlib import Path
from raft.core.observe.alerts.store.runtime_state import AlertRuntime
from raft.core.observe.alerts.store.runtime_store import AlertRuntimeStore
from tests.unit.base import RaftTestCase

class TestRuntimeStore(RaftTestCase):
    def test_roundtrip(self) -> None:
        home = Path(self.tmp_path)
        store = AlertRuntimeStore(home)
        rt = AlertRuntime()
        store.save(rt)
        assert store.load().instances == {}
