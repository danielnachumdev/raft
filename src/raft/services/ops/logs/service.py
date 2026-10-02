"""Operator ``raft logs`` — container stdout/stderr snapshot or follow."""

from __future__ import annotations

import sys
from typing import Optional, TextIO

from ....adapters import DockerStack, Shell
from ....errors import service_not_running
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

    def show(
        self,
        *services: str,
        tail: int = DEFAULT_LOG_TAIL,
        follow: bool = False,
        out: Optional[TextIO] = None,
    ) -> None:
        """Print recent logs, or stream with ``follow`` until interrupted."""
        compose_ids = self._targets.resolve(*services)
        self._require_containers(compose_ids)
        if follow:
            self.docker.follow_compose_logs(*compose_ids, tail=tail)
            return
        self._print_snapshot(compose_ids, tail=tail, out=out)

    def _require_containers(self, compose_ids: tuple[str, ...]) -> None:
        for service in compose_ids:
            if self.docker.try_service_container_id(service) is None:
                raise service_not_running(service)

    def _print_snapshot(
        self,
        compose_ids: tuple[str, ...],
        *,
        tail: int,
        out: Optional[TextIO],
    ) -> None:
        text = self.docker.compose_logs(*compose_ids, tail=tail)
        stream = out if out is not None else sys.stdout
        if text:
            print(text, file=stream)
