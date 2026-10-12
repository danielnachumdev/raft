"""Persist sync pin/SHA files under ``deploy/``."""

from raft.core.core.models.app import App
from raft.core.core.models.stack import Stack


class RefStateWriter:
    """Write ``deploy/<app>.ref`` after a successful git or docker sync."""

    def __init__(self, stack: Stack) -> None:
        self._stack = stack

    def write_git(self, app: App, sha: str, wanted: str) -> None:
        state = self._prepare(app)
        state.write_text(f"{sha}\n# requested: {wanted}\n", encoding="utf-8")

    def write_docker(
        self,
        app: App,
        digest: str,
        pull_ref: str,
        pin: str,
        wanted: str,
    ) -> None:
        state = self._prepare(app)
        state.write_text(
            f"{digest}\n# pulled: {pull_ref}\n# pin: {pin}\n"
            f"# requested: {wanted}\n",
            encoding="utf-8",
        )

    def _prepare(self, app: App):
        state = self._stack.ref_state_file(app)
        state.parent.mkdir(parents=True, exist_ok=True)
        return state
