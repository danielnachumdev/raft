"""Bounded ``docker logs`` fetch — timeout + byte budget for the controller."""

import logging
import subprocess
import time
from typing import Optional

from ..shell import Shell

logger = logging.getLogger(__name__)

# Defaults keep the controller cgroup from buffering multi-day log dumps.
DEFAULT_LOG_FETCH_TIMEOUT_SECONDS = 15.0
DEFAULT_LOG_FETCH_MAX_BYTES = 512 * 1024
DEFAULT_LOG_FETCH_BOOTSTRAP_TAIL = 2000


class BoundedDockerLogs:
    """Fetch timestamped container logs without unbounded ``capture_output``."""

    def __init__(self, shell: Shell) -> None:
        self._sh = shell

    def fetch(
        self,
        name: str,
        *,
        since: str = "",
        timeout: float = DEFAULT_LOG_FETCH_TIMEOUT_SECONDS,
        max_bytes: int = DEFAULT_LOG_FETCH_MAX_BYTES,
        bootstrap_tail: int = DEFAULT_LOG_FETCH_BOOTSTRAP_TAIL,
    ) -> str:
        """Return ``docker logs --timestamps`` text capped by time and bytes.

        Empty ``since`` uses ``--tail`` so a first ship cannot dump container
        history. With ``since``, output is streamed and truncated at
        ``max_bytes`` on a complete line so the cursor can advance and the
        next tick continues without re-holding the backlog in memory.
        """
        if not name:
            return ""
        args = self._args(name, since=since, bootstrap_tail=bootstrap_tail)
        return self._stream(args, timeout=timeout, max_bytes=max_bytes)

    @staticmethod
    def _args(name: str, *, since: str, bootstrap_tail: int) -> list[str]:
        args = ["docker", "logs", "--timestamps"]
        cursor = since.strip()
        if cursor:
            args.extend(["--since", cursor])
        else:
            args.extend(["--tail", str(max(1, bootstrap_tail))])
        args.append(name)
        return args

    def _stream(self, args: list[str], *, timeout: float, max_bytes: int) -> str:
        proc = self._sh.popen(args)
        limit = max(0.1, timeout)
        chunks: list[str] = []
        try:
            total, truncated = self._read_until(
                proc,
                chunks,
                max_bytes=max_bytes,
                deadline=time.monotonic() + limit,
                timeout=limit,
            )
        finally:
            self._stop(proc)
        return self._finish(chunks, truncated=truncated, total=total, max_bytes=max_bytes, args=args)

    def _finish(
        self,
        chunks: list[str],
        *,
        truncated: bool,
        total: int,
        max_bytes: int,
        args: list[str],
    ) -> str:
        text = "".join(chunks)
        if truncated:
            text = self._trim_incomplete_line(text)
            logger.debug(
                "docker logs truncated bytes=%s max=%s cmd=%s", total, max_bytes, args
            )
        return text.strip()

    def _read_until(
        self,
        proc: subprocess.Popen,
        chunks: list[str],
        *,
        max_bytes: int,
        deadline: float,
        timeout: float,
    ) -> tuple[int, bool]:
        total = 0
        stdout = proc.stdout
        if stdout is None:
            return 0, False
        while total < max_bytes:
            line = self._readline(proc, stdout, deadline=deadline, timeout=timeout)
            if line is None:
                break
            added = self._append_line(chunks, line, total=total, max_bytes=max_bytes)
            if added is None:
                return total, True
            total += added
        return total, False

    def _readline(
        self,
        proc: subprocess.Popen,
        stdout,
        *,
        deadline: float,
        timeout: float,
    ) -> Optional[str]:
        if time.monotonic() >= deadline:
            logger.error("command timed out after %ss cmd=%s", timeout, proc.args)
            return None
        line = stdout.readline()
        if line == "" and proc.poll() is not None:
            return None
        if line == "":
            time.sleep(0.01)
            return ""
        return line

    @staticmethod
    def _append_line(
        chunks: list[str], line: str, *, total: int, max_bytes: int
    ) -> Optional[int]:
        if line == "":
            return 0
        size = len(line.encode("utf-8", errors="replace"))
        if total + size > max_bytes:
            return None
        chunks.append(line)
        return size

    @staticmethod
    def _trim_incomplete_line(text: str) -> str:
        if not text or text.endswith("\n"):
            return text
        cut = text.rfind("\n")
        return text if cut < 0 else text[: cut + 1]

    @staticmethod
    def _stop(proc: subprocess.Popen) -> None:
        if proc.poll() is not None:
            return
        try:
            proc.kill()
        except OSError:
            return
        try:
            proc.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass
