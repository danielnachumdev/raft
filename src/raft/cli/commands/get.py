"""Get command helpers (`raft get …`)."""

from typing import Optional

from raft.ui import say


class GetCLI:
    """List or show applied apps (registry desired state)."""

    def __init__(self, stack) -> None:
        self._stack = stack

    def apps(self, *, group: Optional[str] = None) -> None:
        """List applied apps, optionally filtered by ``spec.group`` membership."""
        if not self._stack.apps:
            say("No apps applied. Use: raft apply --file .raft/app.yaml", style="warn")
            return
        filter_group = group.strip() if group else None
        shown = self._print_apps(filter_group)
        if filter_group and shown == 0:
            say(f"No apps in group {filter_group!r}.", style="warn")

    def app(self, name: str) -> None:
        """Show one applied app by metadata.name."""
        self._say_app(self._stack.app(name))

    def _print_apps(self, filter_group: Optional[str]) -> int:
        shown = 0
        for app in self._stack.apps:
            if filter_group and app.group != filter_group:
                continue
            self._say_app(app)
            shown += 1
        return shown

    def _say_app(self, app) -> None:
        group_s = app.group or "-"
        say(f"{app.name}\t{app.source}\t{app.public_host}\t{app.ref}\t{group_s}")
