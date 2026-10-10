from __future__ import annotations

"""Fire subcommand helpers (auth, gate, get)."""

from typing import Any

from ...utils.package_exports import PackageExports

__all__ = ["AuthCLI", "GateCLI", "GetCLI"]

_EXPORTS = PackageExports(
    __name__,
    {
        "AuthCLI": ".auth:AuthCLI",
        "GateCLI": ".gate:GateCLI",
        "GetCLI": ".get:GetCLI",
    },
)


def __getattr__(name: str) -> Any:
    value = _EXPORTS.get(name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
