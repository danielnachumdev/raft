"""Declarative subprocess failure classification."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from .certs_msgs import (
    format_missing_origin_certs,
    looks_like_missing_origin_cert,
    missing_origin_certs_fallback,
)
from .cta import OperatorError, subprocess_detail
from .docker_msgs import (
    compose_failure_message,
    docker_daemon_message,
    docker_pull_failure_message,
    looks_like_docker_daemon_down,
    looks_like_port_in_use,
    port_in_use_message,
)
from .git_msgs import (
    git_auth_failure_message,
    git_generic_failure_message,
    git_network_failure_message,
    looks_like_git_auth_failure,
    looks_like_git_network_failure,
)
from .registry_msgs import (
    looks_like_registry_unauthorized,
    registry_unauthorized_message,
)


@dataclass(frozen=True)
class SubprocessCtx:
    app: Optional[str] = None
    repo: Optional[str] = None
    stack: Any = None
    action: str = ""
    missing_certs: Optional[Sequence[Any]] = None


MatchFn = Callable[[subprocess.CalledProcessError, SubprocessCtx, str], bool]
BuildFn = Callable[[subprocess.CalledProcessError, SubprocessCtx, str], OperatorError]


@dataclass(frozen=True)
class Rule:
    name: str
    match: MatchFn
    build: BuildFn


def _cmd_parts(exc: subprocess.CalledProcessError) -> list[str]:
    return [str(p) for p in (exc.cmd or [])]


def _cmd_text(exc: subprocess.CalledProcessError) -> str:
    return " ".join(_cmd_parts(exc))


def _blob(exc: subprocess.CalledProcessError, detail: str) -> str:
    return f"{_cmd_text(exc)}\n{detail}"


def _match_origin_cert(exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str) -> bool:
    return looks_like_missing_origin_cert(_blob(exc, detail))


def _build_origin_cert(
    exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
) -> OperatorError:
    missing = list(ctx.missing_certs or ())
    if missing:
        return OperatorError(format_missing_origin_certs(missing, include_doctor_footer=False))
    return OperatorError(missing_origin_certs_fallback(detail=detail))


def _match_registry_pull(
    exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
) -> bool:
    cmd = _cmd_text(exc)
    return (
        "docker" in cmd and "pull" in cmd and looks_like_registry_unauthorized(_blob(exc, detail))
    )


def _build_registry_pull(
    exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
) -> OperatorError:
    parts = _cmd_parts(exc)
    image = parts[-1] if parts else "image"
    return OperatorError(
        registry_unauthorized_message(image, detail=detail, app=ctx.app, repo=ctx.repo)
    )


def _match_daemon(exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str) -> bool:
    return looks_like_docker_daemon_down(exc)


def _build_daemon(
    exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
) -> OperatorError:
    return OperatorError(docker_daemon_message(detail=detail))


def _match_port(exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str) -> bool:
    return looks_like_port_in_use(exc)


def _build_port(
    exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
) -> OperatorError:
    return OperatorError(port_in_use_message(detail=detail))


def _match_compose(exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str) -> bool:
    parts = _cmd_parts(exc)
    return "docker" in parts and "compose" in parts


def _build_compose(
    exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
) -> OperatorError:
    action = ctx.action or "run docker compose"
    return OperatorError(compose_failure_message(action, detail=detail))


def _match_git(exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str) -> bool:
    parts = _cmd_parts(exc)
    return bool(parts) and parts[0] == "git"


def _build_git(
    exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
) -> OperatorError:
    parts = _cmd_parts(exc)
    repo = ctx.repo or next(
        (a for a in reversed(parts) if ":" in a or a.endswith(".git")),
        "<repo>",
    )
    if looks_like_git_auth_failure(exc):
        return OperatorError(git_auth_failure_message(repo, app=ctx.app, detail=detail))
    if looks_like_git_network_failure(exc):
        return OperatorError(git_network_failure_message(repo, detail=detail))
    return OperatorError(git_generic_failure_message(repo, app=ctx.app, detail=detail))


def _match_docker_pull(exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str) -> bool:
    cmd = _cmd_text(exc)
    return "docker" in cmd and "pull" in cmd


def _build_docker_pull(
    exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
) -> OperatorError:
    parts = _cmd_parts(exc)
    image = parts[-1] if parts else "image"
    return OperatorError(docker_pull_failure_message(image, detail=detail, app=ctx.app))


SUBPROCESS_RULES: tuple[Rule, ...] = (
    Rule("origin_cert", _match_origin_cert, _build_origin_cert),
    Rule("registry_pull", _match_registry_pull, _build_registry_pull),
    Rule("docker_daemon", _match_daemon, _build_daemon),
    Rule("port_in_use", _match_port, _build_port),
    Rule("compose", _match_compose, _build_compose),
    Rule("git", _match_git, _build_git),
    Rule("docker_pull", _match_docker_pull, _build_docker_pull),
)


def classify_subprocess(
    exc: subprocess.CalledProcessError,
    ctx: Optional[SubprocessCtx] = None,
) -> Optional[OperatorError]:
    """Return an OperatorError when ``exc`` matches a known failure class."""
    context = ctx or SubprocessCtx()
    detail = subprocess_detail(exc)
    for rule in SUBPROCESS_RULES:
        if rule.match(exc, context, detail):
            return rule.build(exc, context, detail)
    return None


def generic_command_failed(exc: subprocess.CalledProcessError) -> OperatorError:
    detail = subprocess_detail(exc)
    cmd = _cmd_text(exc)
    lines = [f"command failed ({exc.returncode}): {cmd}"]
    if detail:
        lines.append(detail)
    return OperatorError("\n".join(lines), has_fix=False)
