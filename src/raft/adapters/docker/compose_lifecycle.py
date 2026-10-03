"""Compose up / down / pull / build for the raft stack."""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from raft.errors import OperatorError, run_compose_checked

from ...models.stack import Stack
from ..shell import Shell
from .project_cleanup import ComposeProjectCleanup

logger = logging.getLogger(__name__)


class DockerComposeLifecycle:
    """Mixin: stack start/stop and image prepare (pull + build).

    Concrete ``DockerStack`` supplies ``enrich_compose_failure`` /
    ``remove_container`` / ``router_network``.
    """

    stack: Stack
    sh: Shell

    def start_stack(self, services: Optional[Sequence[str]] = None) -> None:
        args = self._start_stack_args(services)
        logger.info("compose %s", " ".join(args))
        try:
            run_compose_checked(
                self.sh,
                args,
                action="bring the stack up",
                stream=True,
            )
        except OperatorError as exc:
            raise self.enrich_compose_failure(exc) from exc

    def stop_stack(self) -> None:
        logger.info("compose down --remove-orphans")
        run_compose_checked(
            self.sh,
            ("down", "--remove-orphans"),
            action="bring the stack down",
            stream=True,
        )
        for app in self.stack.apps:
            self.remove_container(app.tmp_container)
        leftover = ComposeProjectCleanup(self.sh).remove_labeled()
        if leftover:
            logger.info("cleared leftover project containers after down: %s", leftover)

    def network_holders(self) -> list:
        """Names still attached to the compose default network."""
        network = self.router_network()
        return ComposeProjectCleanup(self.sh).network_holders(network)

    def pull_services(self, services: Sequence[str]) -> None:
        if not services:
            return
        logger.info("compose pull %s", " ".join(services))
        try:
            run_compose_checked(
                self.sh,
                ("pull", "--ignore-buildable", *services),
                action="pull service images",
                stream=True,
            )
        except OperatorError as exc:
            raise self.enrich_compose_failure(exc, services=services) from exc

    def build_services(self, services: Sequence[str]) -> None:
        if not services:
            return
        logger.info("compose build %s", " ".join(services))
        try:
            run_compose_checked(
                self.sh,
                ("build", *services),
                action="build service images",
                stream=True,
            )
        except OperatorError as exc:
            raise self.enrich_compose_failure(exc, services=services) from exc

    @staticmethod
    def _start_stack_args(services: Optional[Sequence[str]]) -> tuple[str, ...]:
        args: tuple[str, ...] = ("up", "-d", "--build", "--remove-orphans")
        if not services:
            return args
        return args + ("--no-deps", *services)
