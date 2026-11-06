"""CLI package for raft (Google Fire)."""

from raft.services.cli.utils.deps import lazy

__all__ = ["CliExitMapper", "RaftCLI", "RaftCLICommands"]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = lazy.get(name)
    globals()[name] = value
    return value
