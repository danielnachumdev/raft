"""Auth subcommands (`raft auth …`)."""

from typing import Optional

from ..ui import say
from . import deps


def _require_service(service: Optional[str], cmd: str) -> str:
    name = (service or "").strip()
    if not name:
        raise RuntimeError(
            f"auth {cmd} requires SERVICE.\n"
            f"Fix: raft auth {cmd} <app-name> [--repo git@host:owner/repo.git]"
        )
    return name


class AuthCLI:
    """Manage per-service read-only SSH deploy keys for private git sources."""

    def __init__(self, stack) -> None:
        self._stack = stack

    def setup(
        self,
        service: Optional[str] = None,
        force: bool = False,
        repo: Optional[str] = None,
    ) -> None:
        """Generate deploy key + SSH config; print pubkey to paste as a Deploy key.

        Pass ``--repo git@host:owner/name.git`` when the App is not applied yet
        (bootstrap before ``raft apply --git``).
        """
        name = _require_service(service, "setup")
        deps.GitAuthManager(self._stack).setup(name, force=force, repo=repo)

    def list(self) -> None:
        """List services with local deploy keys."""
        auth = deps.GitAuthManager(self._stack)
        names = auth.list_services()
        if not names:
            say("No local raft deploy keys.", style="warn")
            return
        applied = {a.name for a in self._stack.apps}
        for name in names:
            mark = "" if name in applied else " (not applied)"
            say(f"{name}\t{auth.key_path(name)}{mark}")

    def show(self, service: Optional[str] = None, repo: Optional[str] = None) -> None:
        """Print Title + Key (and paste URL) for a service deploy key."""
        name = _require_service(service, "show")
        deps.GitAuthManager(self._stack).show(name, repo=repo)

    def test(self, service: Optional[str] = None, repo: Optional[str] = None) -> None:
        """git ls-remote using the service deploy key."""
        name = _require_service(service, "test")
        deps.GitAuthManager(self._stack).test(name, repo=repo)

    def remove(self, service: Optional[str] = None, keep_key: bool = False) -> None:
        """Remove local key + SSH config stanza for a service."""
        name = _require_service(service, "remove")
        deps.GitAuthManager(self._stack).remove(name, remove_files=not keep_key)
