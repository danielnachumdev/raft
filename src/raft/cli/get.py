"""Get command helpers (`raft get …`)."""

from ..ui import say

def get_apps(stack) -> None:
    """List applied apps."""
    if not stack.apps:
        say("No apps applied. Use: raft apply --file .raft/app.yaml")
        return
    for app in stack.apps:
        say(f"{app.name}\t{app.source}\t{app.public_host}\t{app.ref}")

def get_app(stack, name: str) -> None:
    """Show one applied app by metadata.name."""
    app = stack.app(name)
    say(f"{app.name}\t{app.source}\t{app.public_host}\t{app.ref}")
