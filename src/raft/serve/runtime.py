"""Cross-process ownership of one ``raft serve`` port (flock + pid file)."""

from __future__ import annotations

import fcntl
import os
import signal
import time
from pathlib import Path
from typing import Optional, Tuple

from raft.errors.domain import serve_already_running, serve_stop_failed

SERVE_STATE_DIR = Path("state") / "serve"
_POLL_SECONDS = 0.05
_STOP_WAIT_SECONDS = 5.0


class ServeLease:
    """Exclusive flock held for the lifetime of a foreground ``raft serve``."""

    def __init__(self, path: Path, fd: int) -> None:
        self.path = path
        self.fd = fd
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        try:
            os.ftruncate(self.fd, 0)
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)
            _unlink_quiet(self.path)


class ServeRuntime:
    """Acquire / query / stop a per-port serve lease under the data home."""

    def __init__(self, home: Path) -> None:
        self.home = home

    def lock_path(self, port: int) -> Path:
        return self.home / SERVE_STATE_DIR / f"port-{int(port)}.lock"

    def acquire(self, port: int) -> ServeLease:
        path = self.lock_path(port)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
        if not self._try_lock(fd):
            os.close(fd)
            raise serve_already_running(port)
        self._write_pid(fd, os.getpid())
        return ServeLease(path, fd)

    def stop(self, port: int) -> bool:
        """Terminate the lease holder. Return False when nothing is running."""
        held, pid = self._probe(port)
        if not held:
            return False
        if pid is None:
            raise serve_stop_failed(port, 0, "lock held but pid file is empty")
        self._terminate(pid, port)
        self._wait_until_released(port, pid)
        return True

    def holder_pid(self, port: int) -> Optional[int]:
        held, pid = self._probe(port)
        return pid if held else None

    def _probe(self, port: int) -> Tuple[bool, Optional[int]]:
        """Return ``(held, pid)`` for the port lease (pid may be None if corrupt)."""
        path = self.lock_path(port)
        if not path.is_file():
            return False, None
        fd = os.open(str(path), os.O_RDWR)
        try:
            if self._try_lock(fd):
                self._clear_stale(path, fd)
                return False, None
            return True, self._read_pid(fd)
        finally:
            os.close(fd)

    @staticmethod
    def _try_lock(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False

    @staticmethod
    def _write_pid(fd: int, pid: int) -> None:
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, f"{pid}\n".encode("ascii"))
        os.fsync(fd)

    @staticmethod
    def _read_pid(fd: int) -> Optional[int]:
        os.lseek(fd, 0, os.SEEK_SET)
        raw = os.read(fd, 64).decode("ascii", errors="replace").strip()
        if not raw.isdigit():
            return None
        return int(raw)

    def _clear_stale(self, path: Path, fd: int) -> None:
        os.ftruncate(fd, 0)
        fcntl.flock(fd, fcntl.LOCK_UN)
        _unlink_quiet(path)

    def _terminate(self, pid: int, port: int) -> None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except PermissionError as exc:
            raise serve_stop_failed(port, pid, str(exc)) from exc

    def _wait_until_released(self, port: int, pid: int) -> None:
        """Wait until the flock is free (not until the pid vanishes — zombies linger)."""
        deadline = time.monotonic() + _STOP_WAIT_SECONDS
        while time.monotonic() < deadline:
            if not self._probe(port)[0]:
                return
            time.sleep(_POLL_SECONDS)
        self._kill_force(pid, port)

    def _kill_force(self, pid: int, port: int) -> None:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except PermissionError as exc:
            raise serve_stop_failed(port, pid, str(exc)) from exc
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if not self._probe(port)[0]:
                return
            time.sleep(_POLL_SECONDS)
        raise serve_stop_failed(port, pid, "process did not exit")


def _unlink_quiet(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
