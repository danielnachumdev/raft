"""Auth subcommands (`raft auth …`)."""

from . import deps
from ..ui import say


class AuthCLI:
    """Manage per-service read-only SSH deploy keys for private git sources."""

    def __init__(self, stack) -> None:
        self._stack = stack

    def setup(self, service: str, force: bool = False) -> None:
        """Generate deploy key + SSH config; print pubkey to paste as a Deploy key."""
        deps.GitAuthManager(self._stack).setup(service, force=force)

    def list(self) -> None:
        """List services with local deploy keys."""
        auth = deps.GitAuthManager(self._stack)
        names = auth.list_services()
        if not names:
            say("No local raft deploy keys.")
            return
        applied = {a.name for a in self._stack.apps}
        for name in names:
            mark = "" if name in applied else " (not applied)"
            say(f"{name}\t{auth.key_path(name)}{mark}")

    def show(self, service: str) -> None:
        """Print Title + Key (and paste URL) for a service deploy key."""
        deps.GitAuthManager(self._stack).show(service)

    def test(self, service: str) -> None:
        """git ls-remote using the service deploy key."""
        deps.GitAuthManager(self._stack).test(service)

    def remove(self, service: str, keep_key: bool = False) -> None:
        """Remove local key + SSH config stanza for a service."""
        deps.GitAuthManager(self._stack).remove(service, remove_files=not keep_key)
