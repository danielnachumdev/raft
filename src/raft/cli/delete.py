"""Delete command helpers (`raft delete …`)."""

from . import deps

def delete_app(stack, name: str) -> None:
    """Remove an applied App (metadata.name) from the registry."""
    deps.AppApply(stack).delete(name)
