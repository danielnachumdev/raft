"""Image snapshot/pin helpers and Compose network discovery."""

from __future__ import annotations

import logging

from raft.errors import OperatorError, run_docker_checked

from ...models.app import COMPOSE_PROJECT
from ...models.stack import Stack
from ..shell import Shell

logger = logging.getLogger(__name__)


class DockerImages:
    """Mixin: container image refs/ids and router Compose network."""

    stack: Stack
    sh: Shell

    def container_image_ref(self, container_id: str) -> str:
        named = self._named_image_if_present(container_id)
        if named:
            return named
        tag = f"{COMPOSE_PROJECT}-snapshot:{container_id[:12]}"
        logger.info("committing container %s as %s", container_id[:12], tag)
        run_docker_checked(
            self.sh,
            ("commit", container_id, tag),
            action="snapshot running container for cutover",
            hint="ensure the service is healthy, then: raft redeploy <app>",
        )
        return tag

    def _named_image_if_present(self, container_id: str) -> str:
        try:
            named = run_docker_checked(
                self.sh,
                ("inspect", "-f", "{{.Config.Image}}", container_id),
                action="inspect container image",
            ).stdout.strip()
        except OperatorError:
            return ""
        if not named:
            return ""
        probed = self.sh.docker(
            "image", "inspect", "-f", "{{.Id}}", named, check=False, capture=True
        )
        if probed.returncode == 0 and probed.stdout.strip():
            return named
        return ""

    def container_image_id(self, container_id: str) -> str:
        ref = self.container_image_ref(container_id)
        result = run_docker_checked(
            self.sh,
            ("image", "inspect", "-f", "{{.Id}}", ref),
            action="inspect image id",
        )
        return (result.stdout or "").strip() or ref

    def router_network(self) -> str:
        router_id = self.service_container_id(self.stack.router)
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
        networks = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
        return networks[0] if networks else f"{COMPOSE_PROJECT}_default"
