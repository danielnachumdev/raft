"""InboxReadStore persistence under host/inbox/."""

from unittest.mock import patch

from raft.core.observe.inbox import InboxReadStore
from tests.unit.base import RaftTestCase


class TestInboxReadStore(RaftTestCase):
    def test_mark_prune_and_corrupt(self) -> None:
        store = InboxReadStore(self.tmp_path)
        assert store.list_read_ids() == frozenset()
        store.mark_read(["a", "b", "  "])
        assert store.list_read_ids() == frozenset({"a", "b"})
        store.mark_unread(["a", "  "])
        assert store.list_read_ids() == frozenset({"b"})
        store.prune_to(["b", "c"])
        assert store.list_read_ids() == frozenset({"b"})
        self._assert_corrupt(store)
        self._assert_atomic_cleanup(store)

    def _assert_corrupt(self, store: InboxReadStore) -> None:
        store.path.write_text("[1]\n", encoding="utf-8")
        assert store.list_read_ids() == frozenset()
        store.path.write_text('{"read": "x"}\n', encoding="utf-8")
        assert store.list_read_ids() == frozenset()
        store.path.write_text("{bad", encoding="utf-8")
        assert store.list_read_ids() == frozenset()

    def _assert_atomic_cleanup(self, store: InboxReadStore) -> None:
        with patch("os.replace", side_effect=OSError("boom")):
            try:
                store.mark_read(["z"])
            except OSError:
                pass
        assert list(store.root.glob("*.tmp")) == []
