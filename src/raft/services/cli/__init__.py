"""CLI package for raft (Google Fire)."""

import importlib

__all__ = ["CliExitMapper", "RaftCLI", "RaftCLICommands"]

_EXPORTS = {
    "CliExitMapper": ".exit_mapper:CliExitMapper",
    "RaftCLI": ".cli:RaftCLI",
    "RaftCLICommands": ".commands:RaftCLICommands",
}


def __getattr__(name: str):
    spec = _EXPORTS.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = spec.split(":")
    module = importlib.import_module(module_name, __package__)
    value = getattr(module, attr)
    globals()[name] = value
    return value
