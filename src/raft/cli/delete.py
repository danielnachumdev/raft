"""Delete command helpers (`raft delete …`)."""

from .deps import AppApply


def delete_app(stack, name: str) -> None:
    """Remove an applied App (metadata.name) from the registry."""
    AppApply(stack).delete(name)
