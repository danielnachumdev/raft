"""FifoLock ticket FCFS coverage."""

import threading
import time

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.platform.locking import FifoLock, LockPaths

from tests.unit.base import RaftTestCase
from tests.unit.cta_asserts import CtaAsserts


class TestFifoLock(RaftTestCase):
    @pytest.fixture(autouse=True)
    def _lock_home(self, _raft_base) -> None:
        self.root = self.tmp_path

    def test_reentrant_same_thread(self) -> None:
        with FifoLock(self.root, "demo", timeout=1) as outer:
            with FifoLock(self.root, "demo", timeout=1) as inner:
                assert outer.ticket == 0
                assert inner.reentered is True

    def test_fcfs_grant_order(self) -> None:
        order: list[str] = []
        a_held = threading.Event()
        release_a = threading.Event()
        threads = self._start_fcfs_waiters(order, a_held, release_a)
        release_a.set()
        for t in threads:
            t.join(timeout=5)
        assert order == ["A", "B", "C"]

    def _start_fcfs_waiters(self, order, a_held, release_a):
        paths = LockPaths(self.root)
        t_a = threading.Thread(
            target=self._holder_a, args=(order, a_held, release_a)
        )
        t_a.start()
        assert a_held.wait(timeout=2)
        self._wait_tickets(paths, 1)
        t_b = self._spawn_waiter("B", order)
        self._wait_tickets(paths, 2)
        t_c = self._spawn_waiter("C", order)
        self._wait_tickets(paths, 3)
        return (t_a, t_b, t_c)

    def _holder_a(self, order, a_held, release_a) -> None:
        with FifoLock(self.root, "queue", timeout=5):
            a_held.set()
            release_a.wait(timeout=5)
            order.append("A")

    def _spawn_waiter(self, name: str, order: list) -> threading.Thread:
        def waiter() -> None:
            with FifoLock(self.root, "queue", timeout=5):
                order.append(name)

        t = threading.Thread(target=waiter)
        t.start()
        return t

    @staticmethod
    def _wait_tickets(paths: LockPaths, n: int) -> None:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if len(list(paths.fifo("queue").glob("ticket-*"))) >= n:
                return
            time.sleep(0.01)
        raise AssertionError(f"expected >= {n} fifo tickets")

    def test_busy_times_out(self, caplog: pytest.LogCaptureFixture) -> None:
        held = threading.Event()
        release = threading.Event()
        t = threading.Thread(target=self._hold_fifo, args=(held, release))
        t.start()
        assert held.wait(timeout=2)
        with caplog.at_level("INFO"), pytest.raises(OperatorError) as caught:
            with FifoLock(self.root, "slow", timeout=0.15):
                pass
        CtaAsserts.operator(
            caught.value,
            contains=("fifo-slow", "RAFT_LOCK_TIMEOUT_SECONDS"),
        )
        CtaAsserts.logged(caplog, level="INFO", contains=("waiting for", "fifo-slow"))
        release.set()
        t.join(timeout=2)

    def _hold_fifo(self, held: threading.Event, release: threading.Event) -> None:
        with FifoLock(self.root, "slow", timeout=5):
            held.set()
            release.wait(timeout=5)

    def test_paths_under_locks_dir(self) -> None:
        with FifoLock(self.root, "paths", timeout=1) as lock:
            assert lock.ticket == 0
            assert LockPaths(self.root).fifo("paths").is_dir()
            assert LockPaths(self.root).fifo_ticket("paths", 0).is_file()
        assert not LockPaths(self.root).fifo_ticket("paths", 0).exists()

    def test_corrupt_next_and_junk_ticket_names(self) -> None:
        paths = LockPaths(self.root)
        paths.fifo("junk").mkdir(parents=True, exist_ok=True)
        paths.fifo_next("junk").write_text("not-int\n", encoding="utf-8")
        (paths.fifo("junk") / "ticket-nope").write_text("", encoding="utf-8")
        with FifoLock(self.root, "junk", timeout=1) as lock:
            assert lock.ticket == 0

    def test_empty_next_file_and_missing_dir(self) -> None:
        paths = LockPaths(self.root)
        paths.fifo("empty").mkdir(parents=True, exist_ok=True)
        paths.fifo_next("empty").write_text("\n", encoding="utf-8")
        with FifoLock(self.root, "empty", timeout=1) as lock:
            assert lock.ticket == 0
        missing = FifoLock(self.root, "ghost", timeout=1)
        assert missing._outstanding_tickets() == []

    def test_drop_ticket_oserror_is_swallowed(self, monkeypatch) -> None:
        lock = FifoLock(self.root, "drop", timeout=1)
        lock.ticket = 0
        path = LockPaths(self.root).fifo_ticket("drop", 0)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        monkeypatch.setattr(
            type(path), "unlink", lambda *_a, **_k: (_ for _ in ()).throw(OSError("x"))
        )
        lock._drop_ticket(0)
