"""AlertsLock path."""

from pathlib import Path
from raft.core.platform.locking.alerts_lock import AlertsLock
from raft.core.platform.locking.paths import LockPaths
from tests.unit.base import RaftTestCase


class TestAlertsLock(RaftTestCase):
    def test_path(self) -> None:
        home = Path(self.tmp_path)
        lock = AlertsLock(home)
        assert lock.path == LockPaths(home).alerts()
