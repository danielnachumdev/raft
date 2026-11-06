"""CLI package for raft (Google Fire)."""

from raft.services.cli.utils.deps import CLI_IMPORTS

__all__ = ["CliExitMapper", "RaftCLI", "RaftCLICommands"]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = CLI_IMPORTS.get(name)
    globals()[name] = value
    return value
