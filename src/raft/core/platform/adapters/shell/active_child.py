"""Track the in-flight Shell subprocess so SIGINT/SIGTERM can stop it.

``Shell`` starts children with ``start_new_session=True`` so each child is its
own process-group leader. The terminal's foreground SIGINT therefore reaches
only the raft CLI; this helper forwards SIGTERM (then SIGKILL) to the child's
process group so compose/build work does not continue as an orphan.
"""

import logging
import os
import signal
import subprocess
import threading
from typing import ClassVar, Optional

logger = logging.getLogger(__name__)

_TERM_WAIT_SECONDS = 3.0
_KILL_WAIT_SECONDS = 1.0


class ActiveShellChild:
    """Process-wide registry of the current ``Shell`` child (at most one)."""

    _lock: ClassVar[threading.Lock] = threading.Lock()
    _current: ClassVar[Optional[subprocess.Popen]] = None

    @classmethod
    def register(cls, proc: subprocess.Popen) -> None:
        with cls._lock:
            cls._current = proc

    @classmethod
    def clear(cls, proc: subprocess.Popen) -> None:
        with cls._lock:
            if cls._current is proc:
                cls._current = None

    @classmethod
    def terminate_active(cls) -> None:
        """Best-effort stop of the registered child process group."""
        with cls._lock:
            proc = cls._current
        if proc is None:
            return
        cls.terminate(proc)

    @classmethod
    def terminate(cls, proc: subprocess.Popen) -> None:
        """SIGTERM the child's process group, then SIGKILL if it stays up."""
        if proc.poll() is not None:
            return
        cls._signal_group(proc, signal.SIGTERM)
        if cls._wait(proc, _TERM_WAIT_SECONDS):
            return
        cls._signal_group(proc, signal.SIGKILL)
        cls._wait(proc, _KILL_WAIT_SECONDS)

    @staticmethod
    def _signal_group(proc: subprocess.Popen, signum: int) -> None:
        try:
            os.killpg(proc.pid, signum)
        except ProcessLookupError:
            return
        except PermissionError:
            logger.debug("shell child signal denied pid=%s signum=%s", proc.pid, signum)

    @staticmethod
    def _wait(proc: subprocess.Popen, timeout: float) -> bool:
        try:
            proc.wait(timeout=timeout)
            return True
        except subprocess.TimeoutExpired:
            return False
