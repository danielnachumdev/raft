"""Shared ``docker compose logs -f`` line stream for CLI and serve."""

from __future__ import annotations

import subprocess
import sys
from typing import Iterator, Optional, TextIO

from ..shell import Shell

# Match ``ComposeDiagnostics`` / ``DockerStack`` default when callers omit tail.
_DEFAULT_TAIL = 40


class ComposeLogFollow:
    """Yield Compose follow lines; optionally print them to a terminal."""

    def __init__(self, shell: Shell) -> None:
        self.sh = shell

    def iter_lines(self, *services: str, tail: int = _DEFAULT_TAIL) -> Iterator[str]:
        """Stream log lines until compose exits or the consumer stops iterating."""
        names = [s for s in services if s]
        if not names:
            return
        proc = self._start(names, tail=tail)
        try:
            yield from self._read_lines(proc)
        finally:
            self._stop(proc)

    def to_terminal(
        self,
        *services: str,
        tail: int = _DEFAULT_TAIL,
        out: Optional[TextIO] = None,
    ) -> None:
        """Print follow lines until Ctrl+C or compose exits (CLI ``raft logs -f``)."""
        stream = out if out is not None else sys.stdout
        try:
            for line in self.iter_lines(*services, tail=tail):
                print(line, file=stream, flush=True)
        except KeyboardInterrupt:
            return

    def _start(self, names: list[str], *, tail: int) -> subprocess.Popen:
        return self.sh.popen(
            [
                "docker",
                "compose",
                "logs",
                "-f",
                "--no-color",
                "--tail",
                str(tail),
                *names,
            ]
        )

    @staticmethod
    def _read_lines(proc: subprocess.Popen) -> Iterator[str]:
        stdout = proc.stdout
        if stdout is None:
            return
        for raw in stdout:
            yield raw.rstrip("\n")

    @staticmethod
    def _stop(proc: subprocess.Popen) -> None:
        stdout = proc.stdout
        if stdout is not None and hasattr(stdout, "close"):
            stdout.close()
        if proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
