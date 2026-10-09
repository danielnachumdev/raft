"""Operator ``raft logs`` — container stdout/stderr snapshot or follow."""

from __future__ import annotations

import sys
from typing import Iterator, Optional, TextIO

from ....adapters import DockerStack, Shell
from ....errors.domain import service_not_running
from ....models.stack import Stack
from .targets import LogsTargets

DEFAULT_LOG_TAIL = 100


class Logs:
    """Show Compose service logs (finite tail or follow until Ctrl+C)."""

    def __init__(self, stack: Stack) -> None:
        self.stack = stack
        self.sh = Shell(stack.root)
        self.docker = DockerStack(stack, self.sh)
        self._targets = LogsTargets(stack)

    def bind_stack(self, stack: Stack) -> None:
        """Point at a reloaded Stack after serve registry refresh."""
        self.stack = stack
        self.docker.stack = stack
        self._targets.stack = stack

    def show(
        self,
        *services: str,
        tail: int = DEFAULT_LOG_TAIL,
        follow: bool = False,
        out: Optional[TextIO] = None,
    ) -> None:
        """Print recent logs, or stream with ``follow`` until interrupted."""
        if follow:
            self._print_follow(*services, tail=tail, out=out)
            return
        self._print_snapshot(*services, tail=tail, out=out)

    def snapshot(self, *services: str, tail: int = DEFAULT_LOG_TAIL) -> str:
        """Return recent Compose log text (same resolve/require rules as ``show``)."""
        compose_ids = self._prepare(*services)
        return self.docker.compose_logs(*compose_ids, tail=tail) or ""

    def follow(self, *services: str, tail: int = DEFAULT_LOG_TAIL) -> Iterator[str]:
        """Yield Compose follow lines (CLI ``-f`` and serve SSE share this)."""
        compose_ids = self._prepare(*services)
        return self.docker.iter_follow_compose_logs(*compose_ids, tail=tail)

    def _prepare(self, *services: str) -> tuple[str, ...]:
        compose_ids = self._targets.resolve(*services)
        self._require_containers(compose_ids)
        return compose_ids

    def _require_containers(self, compose_ids: tuple[str, ...]) -> None:
        for service in compose_ids:
            if self.docker.try_service_container_id(service) is None:
                raise service_not_running(service)

    def _print_follow(
        self,
        *services: str,
        tail: int,
        out: Optional[TextIO],
    ) -> None:
        stream = out if out is not None else sys.stdout
        try:
            for line in self.follow(*services, tail=tail):
                print(line, file=stream, flush=True)
        except KeyboardInterrupt:
            return

    def _print_snapshot(
        self,
        *services: str,
        tail: int,
        out: Optional[TextIO],
    ) -> None:
        text = self.snapshot(*services, tail=tail)
        stream = out if out is not None else sys.stdout
        if text:
            print(text, file=stream)
