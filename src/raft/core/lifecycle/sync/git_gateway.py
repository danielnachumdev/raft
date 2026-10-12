"""Raw git CLI via Shell (no product rules)."""

from pathlib import Path
from subprocess import CompletedProcess

from raft.core.platform.adapters.shell import Shell


class GitGateway:
    """Transport-shaped git commands against a working tree or clone URL."""

    def __init__(self, shell: Shell) -> None:
        self._shell = shell

    def clone(self, url: str, dest: Path) -> None:
        self._shell.git("clone", "--quiet", url, str(dest), capture=True)

    def set_remote_url(self, dest: Path, url: str) -> None:
        self._shell.git(
            "remote", "set-url", "origin", url, cwd=dest, capture=True
        )

    def fetch(self, dest: Path) -> None:
        self._shell.git(
            "fetch", "--prune", "--tags", "origin", cwd=dest, capture=True
        )

    def checkout_detach(self, dest: Path, sha: str) -> None:
        self._shell.git(
            "checkout", "-q", "-f", "--detach", sha, cwd=dest, capture=True
        )

    def rev_parse(self, dest: Path, ref: str) -> CompletedProcess:
        return self._shell.git(
            "rev-parse",
            "--verify",
            ref,
            cwd=dest,
            check=False,
            capture=True,
        )

    def status_porcelain(self, dest: Path) -> str:
        result = self._shell.git(
            "status", "--porcelain", cwd=dest, capture=True
        )
        return result.stdout.strip()
