"""Named domain OperatorError factories (declarative call-site CTAs)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence, Union

from .cta import OperatorError, format_cta, operator
from .docker_msgs import nginx_rejected, nginx_reload_failed


def unknown_app(name: str, known: str) -> OperatorError:
    return OperatorError(
        f"unknown app {name!r} (known: {known}).\n"
        f"Fix: raft get apps   # then apply or pick a listed name"
    )


def app_not_applied(name: str, known: str) -> OperatorError:
    return OperatorError(
        f"app {name!r} is not applied (known: {known}).\n"
        f"Fix: raft get apps"
    )


def service_not_running(service: str) -> OperatorError:
    return OperatorError(
        f"service {service!r} is not running — bring the stack up first.\n"
        f"Fix: raft up"
    )


def redeploy_requires_app() -> OperatorError:
    return OperatorError(
        "redeploy requires APP.\n"
        "Fix: raft redeploy <app>|router"
    )


def apply_requires_source() -> OperatorError:
    return OperatorError(
        "apply requires --file PATH or --git URL.\n"
        "Fix: raft apply --file path/to/app.yaml"
    )


def deploy_lock_busy(kind: str, path: Union[Path, str]) -> OperatorError:
    return OperatorError(
        f"another raft operation holds the {kind} lock "
        f"(timed out waiting for {path}).\n"
        f"Fix: wait for the other apply/redeploy/render to finish, then retry; "
        f"or raise RAFT_LOCK_TIMEOUT_SECONDS (default 300)"
    )


def invalid_lock_timeout(raw: object) -> OperatorError:
    return OperatorError(
        f"RAFT_LOCK_TIMEOUT_SECONDS must be a non-negative number, got {raw!r}.\n"
        f"Fix: unset it or set e.g. RAFT_LOCK_TIMEOUT_SECONDS=300"
    )


def auth_requires_service(cmd: str) -> OperatorError:
    return OperatorError(
        f"auth {cmd} requires SERVICE.\n"
        f"Fix: raft auth {cmd} <app-name> [--repo git@host:owner/repo.git]"
    )


def missing_manifest(path: Path) -> OperatorError:
    return OperatorError(
        f"cannot read App manifest: {path}\n"
        f"Fix: pass an existing path (e.g. .raft/app.yaml) or use: "
        f"raft apply --git git@host:owner/repo.git"
    )


def invalid_yaml(path: Union[Path, str], exc: BaseException) -> OperatorError:
    return OperatorError(
        f"invalid YAML in {path}: {exc}\n"
        f"Fix: repair the YAML file"
    )


def filesystem_error(exc: BaseException) -> OperatorError:
    detail = str(exc)
    extra = ""
    if "permission denied" in detail.lower() or getattr(exc, "errno", None) == 13:
        extra = (
            " If raft-controller left root-owned files, fix with:\n"
            '     sudo chown -R "$(whoami):$(whoami)" "${RAFT_DATA_HOME:-$HOME/.raft}"'
        )
    return OperatorError(
        f"filesystem error: {exc}\n"
        f"Fix: check permissions on ~/.raft (or $RAFT_DATA_HOME) and retry.{extra}"
    )


def require_int(
    raw: Any,
    *,
    label: str,
    path: Union[Path, str] = "",
) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        prefix = f"{path}: " if path else ""
        raise OperatorError(
            f"{prefix}{label} must be an integer (1–65535), got {raw!r}.\n"
            f"Fix: use an unquoted number"
        ) from exc


def require_bool(
    raw: Any,
    *,
    label: str,
    path: Union[Path, str] = "",
    default: Optional[bool] = None,
) -> bool:
    if raw is None and default is not None:
        return default
    if not isinstance(raw, bool):
        prefix = f"{path}: " if path else ""
        raise OperatorError(
            f"{prefix}{label} must be a boolean, got {raw!r}.\n"
            f"Fix: use `true` or `false` (unquoted)"
        )
    return raw


def require_mapping(
    raw: Any,
    *,
    label: str,
    path: Union[Path, str] = "",
) -> dict:
    if not isinstance(raw, dict):
        prefix = f"{path}: " if path else ""
        raise OperatorError(
            f"{prefix}{label} must be a YAML mapping, got {type(raw).__name__}.\n"
            f"Fix: use a key/value document"
        )
    return raw


# Re-export nginx factories for domain call sites.
__all__ = [
    "app_not_applied",
    "apply_requires_source",
    "auth_requires_service",
    "deploy_lock_busy",
    "filesystem_error",
    "invalid_lock_timeout",
    "invalid_yaml",
    "missing_manifest",
    "nginx_rejected",
    "nginx_reload_failed",
    "redeploy_requires_app",
    "require_bool",
    "require_int",
    "require_mapping",
    "service_not_running",
    "unknown_app",
]
