"""Docker Compose helpers for the compose stack."""

from __future__ import annotations

import logging
import subprocess

from ..models.app import COMPOSE_PROJECT, App
from ..models.ports import PortSpec
from ..models.stack import Stack
from .shell import Shell

logger = logging.getLogger(__name__)


class DockerStack:
    def __init__(self, stack: Stack, shell: Shell) -> None:
        self.stack = stack
        self.sh = shell

    def start_stack(self) -> None:
        from ..services.command_errors import run_compose_checked

        logger.info("compose up -d --build --remove-orphans")
        run_compose_checked(
            self.sh,
            ("up", "-d", "--build", "--remove-orphans"),
            action="bring the stack up",
        )

    def stop_stack(self) -> None:
        from ..services.command_errors import run_compose_checked

        logger.info("compose down --remove-orphans")
        run_compose_checked(
            self.sh,
            ("down", "--remove-orphans"),
            action="bring the stack down",
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
        from ..services.command_errors import run_compose_checked

        logger.info("force-recreate router")
        run_compose_checked(
            self.sh,
            ("up", "-d", "--no-deps", "--force-recreate", self.stack.router),
            action="recreate router",
        )

    def recreate_gate(self) -> None:
        from ..services.command_errors import run_compose_checked

        logger.info("force-recreate gate (published edge ports)")
        run_compose_checked(
            self.sh,
            ("up", "-d", "--no-deps", "--force-recreate", self.stack.gate),
            action="recreate gate",
            hint="after edge port changes in ~/.raft/settings.yaml",
        )

    def gate_published_ports(self) -> list[int]:
        try:
            cid = self.service_container_id(self.stack.gate)
        except RuntimeError:
            return []
        result = self.sh.docker(
            "inspect",
            "-f",
            "{{range $p, $conf := .NetworkSettings.Ports}}" "{{if $conf}}{{$p}} {{end}}{{end}}",
            cid,
            capture=True,
            check=False,
        )
        if result.returncode != 0:
            return []
        ports: list[int] = []
        for token in (result.stdout or "").split():
            # e.g. 80/tcp
            num = token.split("/", 1)[0]
            if num.isdigit():
                ports.append(int(num))
        return sorted(set(ports))

    def rebuild_service(self, service: str) -> None:
        from ..services.command_errors import run_compose_checked

        logger.info("rebuild service %s", service)
        run_compose_checked(
            self.sh,
            ("up", "-d", "--build", "--no-deps", service),
            action=f"rebuild service {service}",
        )

    def recreate_pulled_service(self, app: App, *, pull_ref: str) -> None:
        from ..services.command_errors import (
            raise_for_docker_pull_failure,
            run_compose_checked,
            run_docker_checked,
        )

        pin = app.compose_pin_image
        logger.info("pull %s then recreate compose service %s (pin %s)", pull_ref, app.name, pin)
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
        run_compose_checked(
            self.sh,
            ("up", "-d", "--no-deps", "--no-build", "--force-recreate", app.name),
            action=f"recreate service {app.name}",
        )

    def service_container_id(self, service: str) -> str:
        from ..services.command_errors import raise_for_compose_failure

        result = self.sh.compose("ps", "-q", service, capture=True, check=False)
        if result.returncode != 0:
            exc = subprocess.CalledProcessError(
                result.returncode,
                ["docker", "compose", "ps", "-q", service],
                output=result.stdout,
                stderr=(result.stderr or "").strip(),
            )
            raise_for_compose_failure(exc, action=f"inspect service {service}")
        cid = (result.stdout or "").strip()
        if not cid:
            raise RuntimeError(
                f"service {service!r} is not running — bring the stack up first.\n"
                f"Fix: raft up"
            )
        return cid

    def container_image_ref(self, container_id: str) -> str:
        from ..services.command_errors import run_docker_checked

        try:
            named = run_docker_checked(
                self.sh,
                ("inspect", "-f", "{{.Config.Image}}", container_id),
                action="inspect container image",
            ).stdout.strip()
        except RuntimeError:
            named = ""
        if named:
            probed = self.sh.docker(
                "image", "inspect", "-f", "{{.Id}}", named, check=False, capture=True
            )
            if probed.returncode == 0 and probed.stdout.strip():
                return named
        tag = f"{COMPOSE_PROJECT}-snapshot:{container_id[:12]}"
        logger.info("committing container %s as %s", container_id[:12], tag)
        try:
            run_docker_checked(
                self.sh,
                ("commit", container_id, tag),
                action="snapshot running container for cutover",
                hint="ensure the service is healthy, then: raft redeploy <app>",
            )
        except RuntimeError as exc:
            raise RuntimeError(
                "could not snapshot the running image for cutover.\n"
                "Fix: ensure the service is healthy, then: raft redeploy <app>\n"
                "     raft doctor"
            ) from exc
        return tag

    def container_image_id(self, container_id: str) -> str:
        from ..services.command_errors import run_docker_checked

        ref = self.container_image_ref(container_id)
        result = run_docker_checked(
            self.sh,
            ("image", "inspect", "-f", "{{.Id}}", ref),
            action="inspect image id",
        )
        return (result.stdout or "").strip() or ref

    def router_network(self) -> str:
        from ..services.command_errors import run_docker_checked

        router_id = self.service_container_id(self.stack.router)
        try:
            result = run_docker_checked(
                self.sh,
                (
                    "inspect",
                    "-f",
                    "{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}",
                    router_id,
                ),
                action="detect compose network",
                hint="raft up / raft doctor",
            )
        except RuntimeError as exc:
            raise RuntimeError(
                "could not detect the compose network.\n"
                "Fix: raft up\n"
                "     raft doctor"
            ) from exc
        networks = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
        return networks[0] if networks else f"{COMPOSE_PROJECT}_default"

    def remove_container(self, name: str) -> None:
        logger.debug("remove container %s", name)
        self.sh.docker("rm", "-f", name, check=False, capture=True)

    def run_tmp(self, *, name: str, alias: str, image: str, network: str) -> None:
        from ..services.command_errors import run_docker_checked

        logger.info("run tmp container name=%s alias=%s image=%s", name, alias, image)
        self.remove_container(name)
        run_docker_checked(
            self.sh,
            (
                "run",
                "-d",
                "--name",
                name,
                "--network",
                network,
                "--network-alias",
                alias,
                "--restart",
                "no",
                image,
            ),
            action=f"start cutover tmp container {name}",
            hint="raft doctor; docker compose ps",
        )

    def router_can_fetch(self, hostname: str, *, port: int = 80) -> bool:
        result = self.sh.compose(
            "exec",
            "-T",
            self.stack.router,
            "wget",
            "-qO-",
            f"http://{hostname}:{port}/",
            check=False,
            capture=True,
        )
        ok = result.returncode == 0
        logger.debug("router_can_fetch %s:%s -> %s", hostname, port, ok)
        return ok

    def reload_router_nginx(self) -> None:
        logger.info("nginx -t && reload on router")
        result = self.sh.compose(
            "exec", "-T", self.stack.router, "nginx", "-t", capture=True, check=False
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            if detail:
                raise RuntimeError(
                    "router nginx rejected the config.\n"
                    f"{detail}\n"
                    "Fix: raft render && raft doctor"
                )
            raise RuntimeError(
                "router nginx rejected the config.\n"
                "Fix: raft render && raft doctor"
            )
        reload = self.sh.compose(
            "exec", "-T", self.stack.router, "nginx", "-s", "reload",
            capture=True, check=False,
        )
        if reload.returncode != 0:
            detail = (reload.stderr or reload.stdout or "").strip()
            raise RuntimeError(
                "router nginx config was valid but reload failed.\n"
                + (f"{detail}\n" if detail else "")
                + "Fix: docker compose -f ~/.raft/compose.yaml restart router"
            )

    def nginx_test_and_reload(self) -> None:
        """Reload router nginx (alias kept for call sites / tests)."""
        self.reload_router_nginx()

    def reload_gate_nginx(self) -> None:
        from ..services.certs import looks_like_missing_origin_cert

        logger.info("nginx -t && reload on gate")
        # Capture stderr so entry/CLI can surface Origin PEM guidance instead of
        # only "command failed: docker compose exec … nginx -t".
        result = self.sh.compose(
            "exec", "-T", self.stack.gate, "nginx", "-t", capture=True, check=False
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            blob = f"nginx -t\n{detail}"
            if looks_like_missing_origin_cert(blob):
                # Preserve CalledProcessError so entry.py can enrich with missing certs.
                raise subprocess.CalledProcessError(
                    result.returncode,
                    ["docker", "compose", "exec", "-T", self.stack.gate, "nginx", "-t"],
                    output=result.stdout,
                    stderr=detail,
                )
            if detail:
                raise RuntimeError(
                    "gate nginx rejected the config.\n"
                    f"{detail}\n"
                    "Fix: raft render && raft doctor"
                )
            raise RuntimeError(
                "gate nginx rejected the config.\n"
                "Fix: raft render && raft doctor"
            )
        reload = self.sh.compose(
            "exec", "-T", self.stack.gate, "nginx", "-s", "reload",
            capture=True, check=False,
        )
        if reload.returncode != 0:
            detail = (reload.stderr or reload.stdout or "").strip()
            raise RuntimeError(
                "gate nginx config was valid but reload failed.\n"
                + (f"{detail}\n" if detail else "")
                + "Fix: raft gate recreate"
            )


    def router_sees_upstream_target(
        self,
        app: App,
        target: str,
        port: PortSpec,
    ) -> bool:
        filename = f"{app.name}-{port.name}.conf"
        result = self.sh.compose(
            "exec",
            "-T",
            self.stack.router,
            "grep",
            "-q",
            target,
            f"/etc/nginx/upstreams/{filename}",
            check=False,
            capture=True,
        )
        return result.returncode == 0
