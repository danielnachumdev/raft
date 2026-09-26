"""Thin checked runners that raise OperatorError via classification."""

from __future__ import annotations

import subprocess
from typing import Any, Optional, Sequence

from .classify import SubprocessCtx, classify_subprocess
from .cta import OperatorError, subprocess_detail
from .docker_msgs import (
    compose_failure_message,
    docker_daemon_message,
    docker_failure_message,
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


def raise_for_compose_failure(
    exc: BaseException,
    *,
    action: str,
    hint: str = "",
) -> None:
    detail = subprocess_detail(exc) if isinstance(exc, subprocess.CalledProcessError) else str(exc)
    if looks_like_docker_daemon_down(exc):
        raise OperatorError(docker_daemon_message(detail=detail)) from exc
    if looks_like_port_in_use(exc):
        raise OperatorError(port_in_use_message(detail=detail)) from exc
    raise OperatorError(
        compose_failure_message(action, detail=detail, hint=hint)
    ) from exc


def raise_for_docker_pull_failure(
    image: str,
    *,
    detail: str = "",
    app: Optional[str] = None,
    repo: Optional[str] = None,
) -> None:
    """Always raise OperatorError for a failed ``docker pull``."""
    if looks_like_registry_unauthorized(detail):
        raise OperatorError(
            registry_unauthorized_message(
                image, detail=detail, app=app, repo=repo
            )
        )
    blob = detail.lower()
    if looks_like_docker_daemon_down(
        subprocess.CalledProcessError(1, ["docker", "pull"], stderr=detail)
    ) or "cannot connect to the docker daemon" in blob:
        raise OperatorError(docker_daemon_message(detail=detail))
    raise OperatorError(
        docker_pull_failure_message(image, detail=detail, app=app)
    )


def raise_for_git_failure(
    exc: BaseException,
    repo: str,
    *,
    app: Optional[str] = None,
    always: bool = False,
) -> None:
    """Re-raise ``exc`` as OperatorError for known git classes."""
    detail = subprocess_detail(exc) if isinstance(exc, subprocess.CalledProcessError) else ""
    if not detail and not isinstance(exc, subprocess.CalledProcessError):
        detail = str(exc)
    if looks_like_git_auth_failure(exc):
        raise OperatorError(
            git_auth_failure_message(repo, app=app, detail=detail)
        ) from exc
    if looks_like_git_network_failure(exc):
        raise OperatorError(
            git_network_failure_message(repo, detail=detail)
        ) from exc
    if always:
        raise OperatorError(
            git_generic_failure_message(repo, app=app, detail=detail)
        ) from exc


def run_compose_checked(
    shell: Any,
    args: Sequence[str],
    *,
    action: str,
    hint: str = "",
    stream: bool = False,
):
    """Run ``docker compose *args``; raise OperatorError on failure.

    When ``stream`` is True, live progress goes to the terminal (no capture).
    """
    result = shell.compose(*args, capture=not stream, check=False)
    if result.returncode == 0:
        return result
    _raise_compose_checked_failure(
        result, args, action=action, hint=hint, stream=stream
    )
    return result  # pragma: no cover


def _raise_compose_checked_failure(
    result: Any,
    args: Sequence[str],
    *,
    action: str,
    hint: str,
    stream: bool,
) -> None:
    if stream:
        # Failure details already printed by compose on the terminal.
        raise OperatorError(
            compose_failure_message(
                action,
                detail="",
                hint=hint or "see docker compose output above",
            )
        )
    exc = subprocess.CalledProcessError(
        result.returncode,
        ["docker", "compose", *args],
        output=result.stdout,
        stderr=(result.stderr or "").strip(),
    )
    raise_for_compose_failure(exc, action=action, hint=hint)


def run_docker_checked(
    shell: Any,
    args: Sequence[str],
    *,
    action: str,
    hint: str = "",
):
    """Run ``docker *args`` with capture; raise OperatorError on failure."""
    result = shell.docker(*args, capture=True, check=False)
    if result.returncode == 0:
        return result
    detail = (result.stderr or result.stdout or "").strip()
    exc = subprocess.CalledProcessError(
        result.returncode,
        ["docker", *args],
        output=result.stdout,
        stderr=detail,
    )
    if looks_like_docker_daemon_down(exc):
        raise OperatorError(docker_daemon_message(detail=detail)) from exc
    raise OperatorError(
        docker_failure_message(action, detail=detail, hint=hint)
    ) from exc


def run_checked(
    runner: Any,
    args: Sequence[str],
    *,
    kind: str,
    action: str,
    hint: str = "",
    ctx: Optional[SubprocessCtx] = None,
):
    """Dispatch to compose/docker checked runners by ``kind``."""
    if kind == "compose":
        return run_compose_checked(runner, args, action=action, hint=hint)
    if kind == "docker":
        return run_docker_checked(runner, args, action=action, hint=hint)
    raise ValueError(f"unsupported run_checked kind: {kind!r}")
