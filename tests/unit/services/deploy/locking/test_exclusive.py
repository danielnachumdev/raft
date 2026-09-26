"""Exclusive flock coverage."""

from __future__ import annotations

import os
import threading
import time
from unittest.mock import patch

import pytest

from raft.errors import OperatorError
from raft.services.deploy.locking import (
    ENV_LOCK_TIMEOUT,
    app_and_stack_locks,
    app_deploy_lock,
    app_lock_path,
    exclusive_lock,
    stack_lock,
    stack_lock_path,
)

from ....base import RaftTestCase
from ....cta_asserts import assert_logged, assert_operator
from .hold import LockHoldThread


class TestExclusiveLock(RaftTestCase):
    @pytest.fixture(autouse=True)
    def _lock_home(self, _raft_base) -> None:
        self.root = self.tmp_path

    def test_reentrant_same_process(self) -> None:
        path = stack_lock_path(self.root)
        with exclusive_lock(path, kind="stack", timeout=1):
            with exclusive_lock(path, kind="stack", timeout=1):
                assert path.is_file()

    def test_busy_times_out(self, caplog: pytest.LogCaptureFixture) -> None:
        path = stack_lock_path(self.root)
        holder = LockHoldThread(path).start()
        try:
            with caplog.at_level("INFO"), pytest.raises(OperatorError) as caught:
                with exclusive_lock(path, kind="stack", timeout=0.15):
                    pass
            assert_operator(
                caught.value,
                contains=("stack", "RAFT_LOCK_TIMEOUT_SECONDS"),
            )
            assert_logged(caplog, level="INFO", contains=("waiting for", "stack"))
            assert not any("acquired" in r.getMessage() for r in caplog.records)
        finally:
            holder.stop()

    def test_waiter_runs_after_holder(self, caplog: pytest.LogCaptureFixture) -> None:
        path = stack_lock_path(self.root)
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
        assert_logged(caplog, level="INFO", contains=("waiting for", "stack"))
        assert_logged(caplog, level="INFO", contains=("acquired", "stack"))

    def _slow(self, path, order, held, release) -> None:
        with exclusive_lock(path, kind="stack", timeout=5):
            order.append("A-start")
            held.set()
            release.wait(timeout=5)
            order.append("A-end")

    def _later(self, path, order, held) -> None:
        assert held.wait(timeout=2)
        with exclusive_lock(path, kind="stack", timeout=5):
            order.append("B")

    def test_app_and_stack_helpers(self) -> None:
        with app_and_stack_locks(self.root, "web", timeout=1):
            assert app_lock_path(self.root, "web").is_file()
            assert stack_lock_path(self.root).is_file()
        with app_deploy_lock(self.root, "web", timeout=1):
            with stack_lock(self.root, timeout=1):
                pass

    def test_app_lock_sanitizes_name(self) -> None:
        assert app_lock_path(self.root, "a/b\\c").name == "app-a_b_c.lock"

    def test_close_errors_during_busy_and_release_are_swallowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = stack_lock_path(self.root)
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
            with exclusive_lock(path, kind="stack", timeout=0.15):
                pass

        assert_operator(caught.value, contains=("stack", "RAFT_LOCK_TIMEOUT_SECONDS"))

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
        with exclusive_lock(path, kind="stack", timeout=1):
            pass
        assert closes["n"] >= 1
