"""Raw docker CLI via Shell (no product rules)."""

import logging
from subprocess import CompletedProcess

from raft.core.platform.adapters.shell import Shell

logger = logging.getLogger(__name__)


class DockerGateway:
    """Transport-shaped image pull / tag / inspect against the Engine."""

    def __init__(self, shell: Shell) -> None:
        self._shell = shell

    def image_present(self, image: str) -> bool:
        """True when ``docker image inspect`` finds the exact ref locally."""
        probed = self._shell.docker(
            "image",
            "inspect",
            "-f",
            "{{.Id}}",
            image,
            check=False,
            capture=True,
        )
        return probed.returncode == 0 and bool((probed.stdout or "").strip())

    def pull(self, image: str) -> CompletedProcess:
        if self.image_present(image):
            logger.info("image %s already present; skip pull", image)
            return CompletedProcess(
                args=["docker", "pull", image],
                returncode=0,
                stdout="",
                stderr="",
            )
        return self._shell.docker("pull", image, capture=True, check=False)

    def tag(self, source: str, target: str) -> None:
        self._shell.docker("tag", source, target)

    def inspect_digest(self, pin: str) -> str:
        return self._shell.docker(
            "image",
            "inspect",
            "-f",
            "{{if .RepoDigests}}{{index .RepoDigests 0}}{{else}}{{.Id}}{{end}}",
            pin,
            capture=True,
        ).stdout.strip()
