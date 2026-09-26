"""Docker Compose helpers for the compose stack."""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from raft.errors import (
    OperatorError,
    raise_for_compose_failure,
    raise_for_docker_pull_failure,
    run_compose_checked,
    run_docker_checked,
)

from ...models.app import App
from ...models.stack import Stack
from .compose_diagnostics import ComposeDiagnostics, DIAG_LOG_TAIL, DIAG_MAX_LINES
from .edge import DockerEdge
from .images import DockerImages
from .inspect import DockerInspect
from ..shell import Shell

logger = logging.getLogger(__name__)


class DockerStack(DockerInspect, DockerImages, DockerEdge):
    def __init__(self, stack: Stack, shell: Shell) -> None:
        self.stack = stack
        self.sh = shell
        self._diagnostics = ComposeDiagnostics(stack, shell, self)

    def start_stack(self) -> None:
        logger.info("compose up -d --build --remove-orphans")
        try:
            run_compose_checked(
                self.sh,
                ("up", "-d", "--build", "--remove-orphans"),
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

    def running_services(self) -> list[str]:
        """Return compose services that are currently running.

        Unknown services (not yet in the rendered compose file) must not raise —
        ``docker compose ps <name>`` exits non-zero when the service is absent.
        """
        running: list[str] = []
        for service in self.stack.core_services:
            result = self.sh.compose(
                "ps",
                "-q",
                "--status",
                "running",
                service,
                capture=True,
                check=False,
            )
            if result.returncode == 0 and (result.stdout or "").strip():
                running.append(service)
        logger.debug("running services: %s", running)
        return running

    def recreate_router(self) -> None:
        logger.info("force-recreate router")
        run_compose_checked(
            self.sh,
            ("up", "-d", "--no-deps", "--force-recreate", self.stack.router),
            action="recreate router",
            stream=True,
        )

    def recreate_gate(self) -> None:
        logger.info("force-recreate gate (published edge ports)")
        run_compose_checked(
            self.sh,
            ("up", "-d", "--no-deps", "--force-recreate", self.stack.gate),
            action="recreate gate",
            hint="after edge port changes in ~/.raft/settings.yaml",
            stream=True,
        )

    def rebuild_service(self, service: str) -> None:
        logger.info("rebuild service %s", service)
        try:
            run_compose_checked(
                self.sh,
                ("up", "-d", "--build", "--no-deps", service),
                action=f"rebuild service {service}",
                stream=True,
            )
        except OperatorError as exc:
            raise self.enrich_compose_failure(exc, services=(service,)) from exc

    def recreate_pulled_service(self, app: App, *, pull_ref: str) -> None:
        pin = app.compose_pin_image
        logger.info(
            "pull %s then recreate compose service %s (pin %s)",
            pull_ref, app.compose_id, pin,
        )
        self._pull_and_tag(app, pull_ref=pull_ref, pin=pin)
        self._force_recreate_service(app.compose_id)

    def _force_recreate_service(self, compose_id: str) -> None:
        try:
            run_compose_checked(
                self.sh,
                (
                    "up", "-d", "--no-deps", "--no-build",
                    "--force-recreate", compose_id,
                ),
                action=f"recreate service {compose_id}",
                stream=True,
            )
        except OperatorError as exc:
            raise self.enrich_compose_failure(exc, services=(compose_id,)) from exc

    def _pull_and_tag(self, app: App, *, pull_ref: str, pin: str) -> None:
        result = self.sh.docker("pull", pull_ref, capture=True, check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise_for_docker_pull_failure(
                pull_ref, detail=detail, app=app.name, repo=app.repo
            )
        if pull_ref != pin:
            run_docker_checked(
                self.sh,
                ("tag", pull_ref, pin),
                action=f"tag {pull_ref} as {pin}",
            )

    def restart_service(self, service: str) -> None:
        """Restart a running service (Compose ``restart``)."""
        logger.info("compose restart %s", service)
        try:
            run_compose_checked(
                self.sh,
                ("restart", service),
                action=f"restart service {service}",
                stream=True,
            )
        except OperatorError as exc:
            raise self.enrich_compose_failure(exc, services=(service,)) from exc

    def stop_service(self, service: str) -> None:
        """Stop a service without removing it (Compose ``stop``)."""
        logger.info("compose stop %s", service)
        try:
            run_compose_checked(
                self.sh,
                ("stop", service),
                action=f"stop service {service}",
                stream=True,
            )
        except OperatorError as exc:
            raise self.enrich_compose_failure(exc, services=(service,)) from exc

    def start_service(self, service: str) -> None:
        """Start / ensure a service is up without rebuild (Compose ``up -d --no-deps``)."""
        logger.info("compose up -d --no-deps %s", service)
        try:
            run_compose_checked(
                self.sh,
                ("up", "-d", "--no-deps", "--no-build", service),
                action=f"start service {service}",
                stream=True,
            )
        except OperatorError as exc:
            raise self.enrich_compose_failure(exc, services=(service,)) from exc

    def remove_container(self, name: str) -> None:
        logger.debug("remove container %s", name)
        self.sh.docker("rm", "-f", name, check=False, capture=True)

    def run_tmp(
        self,
        *,
        name: str,
        alias: str,
        image: str,
        network: str,
        env_file: Optional[str] = None,
    ) -> None:
        logger.info("run tmp container name=%s alias=%s image=%s", name, alias, image)
        self.remove_container(name)
        args = self._tmp_run_args(name, alias, image, network, env_file)
        run_docker_checked(
            self.sh,
            tuple(args),
            action=f"start cutover tmp container {name}",
            hint="raft doctor; docker compose ps",
        )

    @staticmethod
    def _tmp_run_args(
        name: str,
        alias: str,
        image: str,
        network: str,
        env_file: Optional[str],
    ) -> list[str]:
        args: list[str] = [
            "run", "-d", "--name", name, "--network", network,
            "--network-alias", alias, "--restart", "no",
        ]
        if env_file:
            args.extend(["--env-file", env_file])
        args.append(image)
        return args

    def compose_logs(self, *services: str, tail: int = DIAG_LOG_TAIL) -> str:
        """Tail recent Compose logs for ``services`` (declarative log relay)."""
        return self._diagnostics.compose_logs(*services, tail=tail)

    def container_logs(self, name: str, *, tail: int = DIAG_LOG_TAIL) -> str:
        """Tail logs for a named container (e.g. cutover ``_tmp``)."""
        return self._diagnostics.container_logs(name, tail=tail)

    def service_health_summary(self, service: str) -> str:
        """Short status/health (+ last healthcheck output when present)."""
        return self._diagnostics.service_health_summary(service)

    def not_ready_services(self, services: Optional[list[str]] = None) -> list[str]:
        """Compose services that are missing, exited, or unhealthy."""
        return self._diagnostics.not_ready_services(services)

    def diagnostics_for(
        self,
        *services: str,
        containers: Sequence[str] = (),
        tail: int = DIAG_LOG_TAIL,
        max_lines: int = DIAG_MAX_LINES,
    ) -> str:
        """Readable log/health blocks for Compose services and/or containers."""
        return self._diagnostics.diagnostics_for(
            *services, containers=containers, tail=tail, max_lines=max_lines
        )

    def enrich_compose_failure(
        self,
        exc: OperatorError,
        *,
        services: Optional[Sequence[str]] = None,
        detail: str = "",
    ) -> OperatorError:
        """Append recent logs for unhealthy/exited services to a compose CTA."""
        return self._diagnostics.enrich_compose_failure(
            exc, services=services, detail=detail
        )
