"""AtomicText write."""
from pathlib import Path
from raft.core.observe.alerts.store.atomic import AtomicText
from tests.unit.base import RaftTestCase

class TestAtomic(RaftTestCase):
    def test_write(self) -> None:
        path = Path(self.tmp_path) / "host" / "alerts" / "x.txt"
        AtomicText.write(path, "hi", mode=0o600)
        assert path.read_text(encoding="utf-8") == "hi"
