"""InboxLock path."""

from pathlib import Path

from raft.core.platform.locking.inbox_lock import InboxLock
from raft.core.platform.locking.paths import LockPaths
from tests.unit.base import RaftTestCase


class TestInboxLock(RaftTestCase):
    def test_path(self) -> None:
        home = Path(self.tmp_path)
        lock = InboxLock(home)
        assert lock.path == LockPaths(home).inbox()
        assert lock.path.name == "inbox.lock"
