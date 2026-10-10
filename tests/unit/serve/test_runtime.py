"""ServeRuntime flock + pid lease coverage."""

from __future__ import annotations

import fcntl
import multiprocessing as mp
import os
import signal
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from raft.errors.cta import OperatorError
from raft.serve import runtime as runtime_mod
from raft.serve.runtime import ServeRuntime
from raft.serve.service import Serve

from tests.unit.base import RaftTestCase, make_stack


def _hold_until_signal(home: str, port: int, ready: "mp.Queue") -> None:
    ServeRuntime(Path(home)).acquire(port)
    ready.put(os.getpid())
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    while True:
        time.sleep(0.05)


def _spawn_holder(home: Path, port: int) -> mp.Process:
    ready: mp.Queue = mp.Queue()
    proc = mp.Process(
        target=_hold_until_signal,
        args=(str(home), port, ready),
        daemon=True,
    )
    proc.start()
    ready.get(timeout=5)
    return proc


def _ensure_dead(proc: mp.Process) -> None:
    if proc.is_alive():
        proc.kill()
        proc.join(timeout=2)


class TestServeRuntime(RaftTestCase):
    def test_acquire_writes_pid_and_release_unlinks(self) -> None:
        rt = ServeRuntime(self.tmp_path)
        lease = rt.acquire(8787)
        path = rt.lock_path(8787)
        assert path.is_file()
        assert rt.holder_pid(8787) == os.getpid()
        lease.release()
        assert not path.exists()
        assert rt.holder_pid(8787) is None

    def test_second_acquire_raises_already_running(self) -> None:
        rt = ServeRuntime(self.tmp_path)
        lease = rt.acquire(8787)
        try:
            with pytest.raises(OperatorError, match="already running") as caught:
                rt.acquire(8787)
            assert "raft serve --stop" in str(caught.value)
        finally:
            lease.release()

    def test_stop_when_not_running_returns_false(self) -> None:
        assert ServeRuntime(self.tmp_path).stop(8787) is False

    def test_stop_clears_stale_unlocked_pid_file(self) -> None:
        rt = ServeRuntime(self.tmp_path)
        path = rt.lock_path(8787)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("999999\n", encoding="ascii")
        assert rt.stop(8787) is False
        assert not path.exists()

    def test_stop_kills_holder_process(self) -> None:
        proc = _spawn_holder(self.tmp_path, 8791)
        try:
            assert ServeRuntime(self.tmp_path).stop(8791) is True
            proc.join(timeout=5)
            assert not proc.is_alive()
        finally:
            _ensure_dead(proc)

    def test_stop_empty_pid_while_held_raises(self) -> None:
        path = ServeRuntime(self.tmp_path).lock_path(8787)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            with pytest.raises(OperatorError, match="pid file is empty"):
                ServeRuntime(self.tmp_path).stop(8787)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def test_release_is_idempotent(self) -> None:
        lease = ServeRuntime(self.tmp_path).acquire(8787)
        lease.release()
        lease.release()

    def test_terminate_permission_error(self) -> None:
        rt = ServeRuntime(self.tmp_path)
        with patch("raft.serve.runtime.os.kill", side_effect=PermissionError("nope")):
            with pytest.raises(OperatorError, match="could not stop"):
                rt._terminate(12345, 8787)

    def test_terminate_process_lookup_is_ok(self) -> None:
        rt = ServeRuntime(self.tmp_path)
        with patch("raft.serve.runtime.os.kill", side_effect=ProcessLookupError):
            rt._terminate(12345, 8787)

    def test_kill_force_permission_error(self) -> None:
        rt = ServeRuntime(self.tmp_path)
        with patch("raft.serve.runtime.os.kill", side_effect=PermissionError("nope")):
            with pytest.raises(OperatorError, match="could not stop"):
                rt._kill_force(12345, 8787)

    def test_kill_force_lookup_is_ok(self) -> None:
        rt = ServeRuntime(self.tmp_path)
        with patch("raft.serve.runtime.os.kill", side_effect=ProcessLookupError):
            rt._kill_force(12345, 8787)

    def test_kill_force_timeout(self) -> None:
        rt = ServeRuntime(self.tmp_path)
        with patch.object(rt, "_probe", return_value=(True, 1)), patch(
            "raft.serve.runtime.os.kill"
        ), patch("raft.serve.runtime.time.sleep"), patch(
            "raft.serve.runtime.time.monotonic", side_effect=[0.0, 0.5, 2.0]
        ):
            with pytest.raises(OperatorError, match="did not exit"):
                rt._kill_force(12345, 8787)

    def test_kill_force_waits_until_released(self) -> None:
        rt = ServeRuntime(self.tmp_path)
        with patch.object(rt, "_probe", side_effect=[(True, 1), (False, None)]), patch(
            "raft.serve.runtime.os.kill"
        ), patch("raft.serve.runtime.time.sleep"), patch(
            "raft.serve.runtime.time.monotonic", side_effect=[0.0, 0.1, 0.2]
        ):
            rt._kill_force(12345, 8787)

    def test_wait_until_released_escalates(self) -> None:
        rt = ServeRuntime(self.tmp_path)
        # Enter the poll loop once (hits sleep), then expire the deadline.
        with patch.object(rt, "_probe", return_value=(True, 1)), patch.object(
            rt, "_kill_force"
        ) as kill_force, patch(
            "raft.serve.runtime.time.monotonic", side_effect=[0.0, 0.1, 10.0]
        ), patch("raft.serve.runtime.time.sleep") as sleep:
            rt._wait_until_released(8787, 99)
        sleep.assert_called_once()
        kill_force.assert_called_once_with(99, 8787)

    def test_wait_until_released_returns_when_free(self) -> None:
        rt = ServeRuntime(self.tmp_path)
        with patch.object(rt, "_probe", return_value=(False, None)), patch.object(
            rt, "_kill_force"
        ) as kill_force:
            rt._wait_until_released(8787, 99)
        kill_force.assert_not_called()

    def test_wait_until_released_polls_then_returns(self) -> None:
        """Held on first probe → sleep; free on second → return (no force-kill)."""
        rt = ServeRuntime(self.tmp_path)
        with patch.object(
            rt, "_probe", side_effect=[(True, 1), (False, None)]
        ), patch.object(rt, "_kill_force") as kill_force, patch(
            "raft.serve.runtime.time.sleep"
        ) as sleep, patch(
            "raft.serve.runtime.time.monotonic", side_effect=[0.0, 0.1, 0.2]
        ):
            rt._wait_until_released(8787, 99)
        sleep.assert_called_once()
        kill_force.assert_not_called()

    def test_unlink_quiet_swallows_oserror(self) -> None:
        with patch("pathlib.Path.unlink", side_effect=OSError("busy")):
            runtime_mod._unlink_quiet(self.tmp_path / "missing")


class TestServeStopMessages(RaftTestCase):
    def test_stop_when_not_running_message(self, capsys) -> None:
        Serve(make_stack(self.tmp_path)).stop(port=8787)
        assert "not running on 127.0.0.1:8787" in capsys.readouterr().out

    def test_stop_when_running_message(self, capsys) -> None:
        proc = _spawn_holder(self.tmp_path, 8792)
        try:
            Serve(make_stack(self.tmp_path)).stop(port=8792)
            assert "stopped raft serve on 127.0.0.1:8792" in capsys.readouterr().out
            proc.join(timeout=5)
            assert not proc.is_alive()
        finally:
            _ensure_dead(proc)

    def test_run_refuses_when_already_running(self) -> None:
        serve = Serve(make_stack(self.tmp_path))
        lease = serve._runtime.acquire(8787)
        try:
            with pytest.raises(OperatorError, match="already running"):
                serve.run(port=8787)
        finally:
            lease.release()

    def test_run_acquires_lease_around_uvicorn(self) -> None:
        serve = Serve(make_stack(self.tmp_path))
        with patch("raft.serve.service.uvicorn.run") as run:
            serve.run(port=8788)
        run.assert_called_once()
        assert serve._runtime.holder_pid(8788) is None
