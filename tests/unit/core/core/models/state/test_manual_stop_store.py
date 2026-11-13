"""ManualStopStore unit coverage."""

from pathlib import Path

from raft.core.core.models.state.manual_stop_store import ManualStopStore

from tests.unit.base import RaftTestCase


class TestManualStopStore(RaftTestCase):
    def test_mark_clear_and_is_manual_stop(self) -> None:
        store = ManualStopStore(Path(self.tmp_path))
        assert not store.is_manual_stop("demo-api")
        store.mark("demo-api")
        path = self.tmp_path / "services" / "demo-api" / "manual-stop"
        assert path.is_file()
        assert store.is_manual_stop("demo-api")
        store.clear("demo-api")
        assert not path.is_file()
        assert not store.is_manual_stop("demo-api")

    def test_clear_missing_is_noop(self) -> None:
        store = ManualStopStore(Path(self.tmp_path))
        store.clear("demo-api")
        assert not store.is_manual_stop("demo-api")
