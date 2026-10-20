"""Exclusive flock coverage."""

import os
import threading
import time

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.platform.locking import (
    AppAndStackLocks,
    AppDeployLock,
    AppsAndStackLocks,
    ExclusiveLock,
    LockPaths,
    AclLock,
    SettingsLock,
    StackLock,
)

from tests.unit.base import RaftTestCase
from tests.unit.cta_asserts import CtaAsserts
from .hold import LockHoldThread


class TestExclusiveLock(RaftTestCase):
    @pytest.fixture(autouse=True)
    def _lock_home(self, _raft_base) -> None:
        self.root = self.tmp_path
        self.paths = LockPaths(self.root)

    def test_reentrant_same_process(self) -> None:
        path = self.paths.stack()
        with ExclusiveLock(path, kind="stack", timeout=1):
            with ExclusiveLock(path, kind="stack", timeout=1):
                assert path.is_file()

    def test_busy_times_out(self, caplog: pytest.LogCaptureFixture) -> None:
        path = self.paths.stack()
        holder = LockHoldThread(path).start()
        try:
            with caplog.at_level("INFO"), pytest.raises(OperatorError) as caught:
                with ExclusiveLock(path, kind="stack", timeout=0.15):
                    pass
            CtaAsserts.operator(
                caught.value,
                contains=("stack", "RAFT_LOCK_TIMEOUT_SECONDS"),
            )
            CtaAsserts.logged(caplog, level="INFO", contains=("waiting for", "stack"))
            assert not any("acquired" in r.getMessage() for r in caplog.records)
        finally:
            holder.stop()

    def test_waiter_runs_after_holder(self, caplog: pytest.LogCaptureFixture) -> None:
        path = self.paths.stack()
        order: list[str] = []
        held = threading.Event()
        release = threading.Event()
        t_a = threading.Thread(target=self._slow, args=(path, order, held, release))
        t_b = threading.Thread(target=self._later, args=(path, order, held))
        with caplog.at_level("INFO"):
            t_a.start()
            t_b.start()
            time.sleep(0.05)
            release.set()
            t_a.join(timeout=2)
            t_b.join(timeout=2)

        assert order == ["A-start", "A-end", "B"]
        CtaAsserts.logged(caplog, level="INFO", contains=("waiting for", "stack"))
        CtaAsserts.logged(caplog, level="INFO", contains=("acquired", "stack"))

    def _slow(self, path, order, held, release) -> None:
        with ExclusiveLock(path, kind="stack", timeout=5):
            order.append("A-start")
            held.set()
            release.wait(timeout=5)
            order.append("A-end")

    def _later(self, path, order, held) -> None:
        assert held.wait(timeout=2)
        with ExclusiveLock(path, kind="stack", timeout=5):
            order.append("B")

    def test_app_and_stack_helpers(self) -> None:
        with AppAndStackLocks(self.root, "web", timeout=1):
            assert self.paths.app("web").is_file()
            assert self.paths.stack().is_file()
        with AppDeployLock(self.root, "web", timeout=1):
            with StackLock(self.root, timeout=1):
                pass

    def test_apps_and_stack_locks_sorted(self) -> None:
        with AppsAndStackLocks(self.root, ("web", "api", ""), timeout=1):
            assert self.paths.app("api").is_file()
            assert self.paths.app("web").is_file()
            assert self.paths.stack().is_file()

    def test_app_lock_sanitizes_name(self) -> None:
        assert self.paths.app("a/b\\c").name == "app-a_b_c.lock"

    def test_settings_lock_helper(self) -> None:
        with SettingsLock(self.root, timeout=1):
            assert self.paths.settings().name == "settings.lock"
            assert self.paths.settings().is_file()

    def test_acl_lock_helper(self) -> None:
        with AclLock(self.root, timeout=1):
            assert self.paths.acl().name == "acl.lock"
            assert self.paths.acl().is_file()

    def test_close_errors_during_busy_and_release_are_swallowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = self.paths.stack()
        holder = LockHoldThread(path).start()
        try:
            self._flaky_close_timeout(path, monkeypatch)
        finally:
            holder.stop()
        self._flaky_close_success(path, monkeypatch)

    def _flaky_close_timeout(self, path, monkeypatch) -> None:
        real_close = os.close
        closes = {"n": 0}

        def flaky_close(fd: int) -> None:
            closes["n"] += 1
            if closes["n"] <= 2:
                raise OSError("simulated close failure")
            real_close(fd)

        monkeypatch.setattr(os, "close", flaky_close)
        with pytest.raises(OperatorError) as caught:
            with ExclusiveLock(path, kind="stack", timeout=0.15):
                pass

        CtaAsserts.operator(caught.value, contains=("stack", "RAFT_LOCK_TIMEOUT_SECONDS"))

    def _flaky_close_success(self, path, monkeypatch) -> None:
        real_close = os.close
        closes = {"n": 0}

        def flaky_close(fd: int) -> None:
            closes["n"] += 1
            if closes["n"] <= 2:
                raise OSError("simulated close failure")
            real_close(fd)

        monkeypatch.setattr(os, "close", flaky_close)
        closes["n"] = 0
        with ExclusiveLock(path, kind="stack", timeout=1):
            pass
        assert closes["n"] >= 1
