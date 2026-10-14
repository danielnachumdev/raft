"""Operator ``raft logs`` — retained snapshot or live Compose follow."""

import sys
from typing import Iterator, Optional, TextIO

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.config.settings.types import ServiceLogsConfig
from raft.core.core.errors.domain import DomainErrors
from raft.core.core.models.stack import Stack
from raft.core.platform.adapters.docker.stack import DockerStack
from raft.core.platform.adapters.shell import Shell

from .reader import ServiceLogsReader
from .store import ServiceLogsStore
from .targets import LogsTargets

DEFAULT_LOG_TAIL = 100


class Logs:
    """Show Compose service logs (retained snapshot or live follow)."""

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
        """Return retained (or Docker-fallback) log text; empty when none."""
        compose_ids = self._targets.resolve(*services)
        chunks = [self._snapshot_one(cid, tail=tail) for cid in compose_ids]
        return "\n".join(part for part in chunks if part)

    def follow(self, *services: str, tail: int = DEFAULT_LOG_TAIL) -> Iterator[str]:
        """Yield Compose follow lines (CLI ``-f`` and serve SSE share this)."""
        compose_ids = self._targets.resolve(*services)
        self._require_containers(compose_ids)
        return self.docker.iter_follow_compose_logs(*compose_ids, tail=tail)

    def _snapshot_one(self, compose_id: str, *, tail: int) -> str:
        retained = self._retained_tail(compose_id, tail=tail)
        if retained:
            return retained
        if self.docker.try_service_container_id(compose_id) is None:
            return ""
        return self.docker.compose_logs(compose_id, tail=tail) or ""

    def _retained_tail(self, compose_id: str, *, tail: int) -> str:
        cfg = self._service_logs_config()
        store = ServiceLogsStore(
            self.stack.root,
            max_age_days=cfg.retention_max_age_days,
            max_bytes=cfg.retention_max_bytes,
        )
        return ServiceLogsReader(store).tail(compose_id, lines=tail)

    def _service_logs_config(self) -> ServiceLogsConfig:
        return SettingsLoader().load(self.stack.root).service_logs

    def _require_containers(self, compose_ids: tuple[str, ...]) -> None:
        for service in compose_ids:
            if self.docker.try_service_container_id(service) is None:
                raise DomainErrors.service_not_running(service)

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
