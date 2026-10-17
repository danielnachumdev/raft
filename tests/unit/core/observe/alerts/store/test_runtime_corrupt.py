"""Runtime store corrupt paths."""
import json
from pathlib import Path
from raft.core.observe.alerts.store.runtime_store import AlertRuntimeStore
from tests.unit.base import RaftTestCase

class TestRuntimeCorrupt(RaftTestCase):
    def test_bad_json_quarantine(self) -> None:
        home = Path(self.tmp_path)
        path = home / "state" / "alerts" / "runtime.json"
        path.parent.mkdir(parents=True)
        path.write_text("{bad", encoding="utf-8")
        rt = AlertRuntimeStore(home).load()
        assert rt.instances == {}

    def test_non_mapping(self) -> None:
        home = Path(self.tmp_path)
        path = home / "state" / "alerts" / "runtime.json"
        path.parent.mkdir(parents=True)
        path.write_text("[]", encoding="utf-8")
        assert AlertRuntimeStore(home).load().instances == {}
