"""Docker Compose helpers for the compose stack."""

from __future__ import annotations

import logging

from ..models.inventory import COMPOSE_PROJECT, App, Stack
from .shell import Shell

logger = logging.getLogger(__name__)


class DockerStack:
    def __init__(self, stack: Stack, shell: Shell) -> None:
        self.stack = stack
        self.sh = shell

    def start_stack(self) -> None:
        logger.info("compose up -d --build --remove-orphans")
        self.sh.compose("up", "-d", "--build", "--remove-orphans")

    def stop_stack(self) -> None:
        logger.info("compose down --remove-orphans")
        self.sh.compose("down", "--remove-orphans")
        for app in self.stack.apps:
            self.remove_container(app.tmp_container)

    def running_services(self) -> list[str]:
        running: list[str] = []
        for service in self.stack.core_services:
            result = self.sh.compose("ps", "-q", "--status", "running", service, capture=True)
            if (result.stdout or "").strip():
                running.append(service)
        logger.debug("running services: %s", running)
        return running

    def recreate_router(self) -> None:
        logger.info("force-recreate router")
        self.sh.compose("up", "-d", "--no-deps", "--force-recreate", self.stack.router)

    def rebuild_service(self, service: str) -> None:
        logger.info("rebuild service %s", service)
        self.sh.compose("up", "-d", "--build", "--no-deps", service)

    def recreate_pulled_service(self, app: App, *, pull_ref: str) -> None:
        """Pull ``pull_ref``, retag to the Compose pin (inventory default ref), recreate."""
        pin = app.compose_pin_image
        logger.info("pull %s then recreate compose service %s (pin %s)", pull_ref, app.name, pin)
        self.sh.docker("pull", pull_ref)
        if pull_ref != pin:
            self.sh.docker("tag", pull_ref, pin)
        self.sh.compose("up", "-d", "--no-deps", "--no-build", "--force-recreate", app.name)

    def service_container_id(self, service: str) -> str:
        result = self.sh.compose("ps", "-q", service, capture=True)
        cid = (result.stdout or "").strip()
        if not cid:
            raise RuntimeError(
                f"service {service!r} is not running — bring the stack up first"
            )
        return cid

    def container_image_ref(self, container_id: str) -> str:
        named = self.sh.docker(
            "inspect", "-f", "{{.Config.Image}}", container_id, capture=True
        ).stdout.strip()
        if named:
            probed = self.sh.docker(
                "image", "inspect", "-f", "{{.Id}}", named, check=False, capture=True
            )
            if probed.returncode == 0 and probed.stdout.strip():
                return named
        tag = f"{COMPOSE_PROJECT}-snapshot:{container_id[:12]}"
        logger.info("committing container %s as %s", container_id[:12], tag)
        self.sh.docker("commit", container_id, tag, capture=True)
        return tag

    def container_image_id(self, container_id: str) -> str:
        ref = self.container_image_ref(container_id)
        result = self.sh.docker("image", "inspect", "-f", "{{.Id}}", ref, capture=True)
        return (result.stdout or "").strip() or ref

    def router_network(self) -> str:
        router_id = self.service_container_id(self.stack.router)
        result = self.sh.docker(
            "inspect",
            "-f",
            "{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}",
            router_id,
            capture=True,
        )
        networks = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
        return networks[0] if networks else f"{COMPOSE_PROJECT}_default"

    def remove_container(self, name: str) -> None:
        logger.debug("remove container %s", name)
        self.sh.docker("rm", "-f", name, check=False, capture=True)

    def run_tmp(self, *, name: str, alias: str, image: str, network: str) -> None:
        logger.info("run tmp container name=%s alias=%s image=%s", name, alias, image)
        self.remove_container(name)
        self.sh.docker(
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
            capture=True,
        )

    def router_can_fetch(self, hostname: str) -> bool:
        result = self.sh.compose(
            "exec",
            "-T",
            self.stack.router,
            "wget",
            "-qO-",
            f"http://{hostname}:80/",
            check=False,
            capture=True,
        )
        ok = result.returncode == 0
        logger.debug("router_can_fetch %s -> %s", hostname, ok)
        return ok

    def nginx_test_and_reload(self) -> None:
        logger.info("nginx -t && reload on router")
        self.sh.compose("exec", "-T", self.stack.router, "nginx", "-t")
        self.sh.compose("exec", "-T", self.stack.router, "nginx", "-s", "reload")

    def router_sees_upstream_target(self, app: App, target: str) -> bool:
        result = self.sh.compose(
            "exec",
            "-T",
            self.stack.router,
            "grep",
            "-q",
            target,
            f"/etc/nginx/upstreams/{app.name}.conf",
            check=False,
            capture=True,
        )
        return result.returncode == 0
