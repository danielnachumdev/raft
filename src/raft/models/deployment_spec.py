"""Per-app deploy transition contract (``spec.deployment``)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from raft.errors.cta import OperatorError, operator

DEFAULT_DEPLOYMENT_METHOD = "seamless"
DEPLOYMENT_METHODS = frozenset({"seamless", "inplace"})
_KNOWN_KEYS = frozenset({"method"})


@dataclass(frozen=True)
class DeploymentSpec:
    """How apply/redeploy replaces a running generation. Default method is seamless."""

    method: str = DEFAULT_DEPLOYMENT_METHOD


class DeploymentSpecParser:
    """Parse and validate ``spec.deployment`` from an App manifest."""

    @classmethod
    def parse(cls, spec: dict[str, Any], path: Path) -> DeploymentSpec:
        raw = spec.get("deployment")
        if raw is None:
            return DeploymentSpec()
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: spec.deployment must be an object")
        cls._reject_unknown(raw, path)
        return DeploymentSpec(method=cls._method(raw, path))

    @classmethod
    def _method(cls, raw: dict[str, Any], path: Path) -> str:
        if "method" not in raw:
            return DEFAULT_DEPLOYMENT_METHOD
        value = raw.get("method")
        if not isinstance(value, str) or not value.strip():
            raise cls._bad_method(path, value)
        method = value.strip().lower()
        if method not in DEPLOYMENT_METHODS:
            raise cls._bad_method(path, method)
        return method

    @classmethod
    def _reject_unknown(cls, raw: dict[str, Any], path: Path) -> None:
        unknown = sorted(set(raw) - _KNOWN_KEYS)
        if not unknown:
            return
        keys = ", ".join(unknown)
        raise ValueError(
            f"{path}: spec.deployment unknown keys: {keys}. "
            f"Fix: remove unknown keys from deployment (method)"
        )

    @staticmethod
    def _bad_method(path: Path, value: Any) -> OperatorError:
        allowed = ", ".join(sorted(DEPLOYMENT_METHODS))
        return operator(
            f"{path}: spec.deployment.method must be one of {allowed}, "
            f"got {value!r}.",
            [
                f"set spec.deployment.method to seamless or inplace "
                f"(omit deployment for default {DEFAULT_DEPLOYMENT_METHOD})",
            ],
        )
