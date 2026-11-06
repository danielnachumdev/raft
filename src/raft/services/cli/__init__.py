"""CLI package for raft (Google Fire)."""

from raft.services.cli.utils import deps as _deps

__all__ = ["CliExitMapper", "RaftCLI", "RaftCLICommands"]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(_deps, name)._load()
    globals()[name] = value
    return value
