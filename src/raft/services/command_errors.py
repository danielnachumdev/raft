"""Docker / Compose failure classification for operator CTAs."""

from __future__ import annotations

import subprocess
from typing import Optional, Sequence


def _blob(exc: BaseException) -> str:
    text = str(exc).lower()
    if isinstance(exc, subprocess.CalledProcessError):
        text = f"{text} {(exc.stderr or '')} {(exc.output or '')}".lower()
    return text


def _first_line(detail: str) -> str:
    stripped = detail.strip()
    if not stripped:
        return ""
    return stripped.splitlines()[0].strip()


def looks_like_docker_daemon_down(exc: BaseException) -> bool:
    text = _blob(exc)
    return (
        "cannot connect to the docker daemon" in text
        or "is the docker daemon running" in text
        or "permission denied while trying to connect to the docker api" in text
    )


def looks_like_port_in_use(exc: BaseException) -> bool:
    text = _blob(exc)
    return (
        "address already in use" in text
        or "port is already allocated" in text
        or "bind: address already in use" in text
    )


def docker_daemon_message(*, detail: str = "") -> str:
    lines = [
        "cannot talk to the Docker daemon.",
        "",
        "Fix:",
        "  1. start Docker (e.g. sudo systemctl start docker)",
        "  2. ensure your user is in the docker group, then re-login",
        "  3. raft doctor",
    ]
    first = _first_line(detail)
    if first:
        lines.extend(["", f"(docker: {first})"])
    return "\n".join(lines)


def port_in_use_message(*, detail: str = "") -> str:
    lines = [
        "a published port is already in use on this VPS.",
        "",
        "Fix:",
        "  1. stop the other process, or change edge ports in ~/.raft/settings.yaml",
        "  2. raft gate recreate   # after edge port changes",
        "  3. raft doctor",
    ]
    first = _first_line(detail)
    if first:
        lines.extend(["", f"(docker: {first})"])
    return "\n".join(lines)


def compose_failure_message(
    action: str,
    *,
    detail: str = "",
    hint: str = "",
) -> str:
    lines = [
        f"docker compose failed while trying to {action}.",
        "",
        "Fix:",
        "  1. raft doctor",
        "  2. docker compose -f ~/.raft/compose.yaml ps",
        "  3. docker compose -f ~/.raft/compose.yaml logs --tail=80 gate router",
    ]
    if hint:
        lines.insert(3, f"  hint: {hint}")
    first = _first_line(detail)
    if first:
        lines.extend(["", f"(docker: {first})"])
    return "\n".join(lines)


def raise_for_compose_failure(
    exc: BaseException,
    *,
    action: str,
    hint: str = "",
) -> None:
    detail = ""
    if isinstance(exc, subprocess.CalledProcessError):
        detail = (exc.stderr or exc.output or "").strip()
    if looks_like_docker_daemon_down(exc):
        raise RuntimeError(docker_daemon_message(detail=detail)) from exc
    if looks_like_port_in_use(exc):
        raise RuntimeError(port_in_use_message(detail=detail)) from exc
    raise RuntimeError(
        compose_failure_message(action, detail=detail, hint=hint)
    ) from exc


def run_compose_checked(
    shell,
    args: Sequence[str],
    *,
    action: str,
    hint: str = "",
):
    """Run ``docker compose *args`` with capture; raise RuntimeError on failure."""
    result = shell.compose(*args, capture=True, check=False)
    if result.returncode == 0:
        return result
    exc = subprocess.CalledProcessError(
        result.returncode,
        ["docker", "compose", *args],
        output=result.stdout,
        stderr=(result.stderr or "").strip(),
    )
    raise_for_compose_failure(exc, action=action, hint=hint)
    return result  # pragma: no cover


def looks_like_image_missing(exc: BaseException) -> bool:
    text = _blob(exc)
    return (
        "not found" in text
        or "manifest unknown" in text
        or "no such image" in text
        or "pull access denied" in text
    )


def docker_pull_failure_message(
    image: str,
    *,
    detail: str = "",
    app: Optional[str] = None,
) -> str:
    svc = app or "<app-name>"
    lines = [
        f"docker pull failed for {image!r}.",
        "",
        "Fix:",
        "  1. docker login <registry>   # if the image is private",
        f"  2. raft sync {svc}",
        "  3. raft doctor",
    ]
    first = _first_line(detail)
    if first:
        lines.extend(["", f"(docker: {first})"])
    return "\n".join(lines)


def raise_for_docker_pull_failure(
    image: str,
    *,
    detail: str = "",
    app: Optional[str] = None,
    repo: Optional[str] = None,
) -> None:
    """Always raise RuntimeError for a failed ``docker pull``."""
    from .registry import (
        looks_like_registry_unauthorized,
        registry_unauthorized_message,
    )

    if looks_like_registry_unauthorized(detail):
        raise RuntimeError(
            registry_unauthorized_message(
                image, detail=detail, app=app, repo=repo
            )
        )
    blob = detail.lower()
    if looks_like_docker_daemon_down(
        subprocess.CalledProcessError(1, ["docker", "pull"], stderr=detail)
    ) or "cannot connect to the docker daemon" in blob:
        raise RuntimeError(docker_daemon_message(detail=detail))
    raise RuntimeError(
        docker_pull_failure_message(image, detail=detail, app=app)
    )


def run_docker_checked(
    shell,
    args: Sequence[str],
    *,
    action: str,
    hint: str = "",
):
    """Run ``docker *args`` with capture; raise RuntimeError on failure."""
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
        raise RuntimeError(docker_daemon_message(detail=detail)) from exc
    lines = [
        f"docker failed while trying to {action}.",
        "",
        "Fix:",
        "  1. raft doctor",
        "  2. docker ps -a",
    ]
    if hint:
        lines.insert(3, f"  hint: {hint}")
    first = _first_line(detail)
    if first:
        lines.extend(["", f"(docker: {first})"])
    raise RuntimeError("\n".join(lines)) from exc
