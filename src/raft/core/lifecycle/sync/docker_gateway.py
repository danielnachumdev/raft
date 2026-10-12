"""Raw docker CLI via Shell (no product rules)."""

from subprocess import CompletedProcess

from raft.core.platform.adapters.shell import Shell


class DockerGateway:
    """Transport-shaped image pull / tag / inspect against the Engine."""

    def __init__(self, shell: Shell) -> None:
        self._shell = shell

    def pull(self, image: str) -> CompletedProcess:
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
