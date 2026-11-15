"""Bounded ``docker logs`` fetch — timeout + byte budget for the controller."""

import logging
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

from ..shell import Shell
from .logs_tail_coverage import LogsTailCoverage

logger = logging.getLogger(__name__)

# Defaults keep the controller cgroup from buffering multi-day log dumps.
DEFAULT_LOG_FETCH_TIMEOUT_SECONDS = 15.0
DEFAULT_LOG_FETCH_MAX_BYTES = 512 * 1024
DEFAULT_LOG_FETCH_BOOTSTRAP_TAIL = 2000
# Shipper revisits each service every few seconds; a short tail usually reaches
# the cursor, and ``docker logs`` cost grows with every line it emits.
LOG_FETCH_RECENT_TAIL = 500


@dataclass(frozen=True)
class StreamedLogs:
    text: str
    complete: bool


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
        history. With ``since``, a ``--tail`` slice is tried first: json-file
        ``--since`` re-scans the whole log file (seconds on large logs), while
        ``--tail`` reads from the end. Only when that slice does not reach back
        to ``since`` is the full ``--since`` stream used, truncated at
        ``max_bytes`` on a complete line so the cursor can advance.
        """
        if not name:
            return ""
        cursor = since.strip()
        if cursor:
            recent = self._tail_reaching(
                name, cursor, tail=bootstrap_tail, timeout=timeout, max_bytes=max_bytes
            )
            if recent is not None:
                return recent
        args = self._args(name, since=since, bootstrap_tail=bootstrap_tail)
        return self._stream(args, timeout=timeout, max_bytes=max_bytes).text

    def _tail_reaching(
        self, name: str, cursor: str, *, tail: int, timeout: float, max_bytes: int
    ) -> Optional[str]:
        args = self._args(
            name, since="", bootstrap_tail=min(tail, LOG_FETCH_RECENT_TAIL)
        )
        result = self._stream(args, timeout=timeout, max_bytes=max_bytes)
        if result.complete and LogsTailCoverage.reaches(result.text, cursor):
            return result.text
        return None

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

    def _stream(
        self, args: list[str], *, timeout: float, max_bytes: int
    ) -> StreamedLogs:
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
            complete = not truncated and total < max_bytes and proc.poll() == 0
        finally:
            self._stop(proc)
        text = self._finish(
            chunks, truncated=truncated, total=total, max_bytes=max_bytes, args=args
        )
        return StreamedLogs(text=text, complete=complete)

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
