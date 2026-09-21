"""Get command helpers (`raft get …`)."""

from typing import Optional

from raft.errors import OperatorError

from ..ui import say


def get_apps(stack, *, group: Optional[str] = None) -> None:
    """List applied apps, optionally filtered by ``spec.groups`` membership."""
    if not stack.apps:
        say("No apps applied. Use: raft apply --file .raft/app.yaml", style="warn")
        return
    filter_group = group.strip() if group else None
    shown = 0
    for app in stack.apps:
        try:
            groups = stack.spec_for(app).groups
        except (ValueError, FileNotFoundError, OperatorError):
            groups = ()
        if filter_group and filter_group not in groups:
            continue
        groups_s = ",".join(groups) if groups else "-"
        say(f"{app.name}\t{app.source}\t{app.public_host}\t{app.ref}\t{groups_s}")
        shown += 1
    if filter_group and shown == 0:
        say(f"No apps in group {filter_group!r}.", style="warn")


def get_app(stack, name: str) -> None:
    """Show one applied app by metadata.name."""
    app = stack.app(name)
    try:
        groups = stack.spec_for(app).groups
    except (ValueError, FileNotFoundError, OperatorError):
        groups = ()
    groups_s = ",".join(groups) if groups else "-"
    say(f"{app.name}\t{app.source}\t{app.public_host}\t{app.ref}\t{groups_s}")
