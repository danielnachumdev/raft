"""Host resource exhaustion CTAs (OOM / disk) for Docker apply paths."""

from __future__ import annotations

import subprocess
from typing import Optional

from .cta import OperatorError, exc_blob, format_cta, subprocess_detail

_OOM_MARKERS = (
    "out of memory",
    "cannot allocate memory",
    "oom-kill",
    "oom_kill",
    "oomkilled",
    "oom killed",
    "memory cgroup out of memory",
    "killed by the oom",
    "insufficient memory",
)

_DISK_MARKERS = (
    "no space left on device",
    "enospc",
    "errno 28",
)


def looks_like_host_oom(text: str) -> bool:
    lower = (text or "").lower()
    return any(marker in lower for marker in _OOM_MARKERS)


def looks_like_disk_full(text: str) -> bool:
    lower = (text or "").lower()
    return any(marker in lower for marker in _DISK_MARKERS)


def looks_like_host_oom_exc(exc: BaseException) -> bool:
    if looks_like_host_oom(_resource_blob(exc)):
        return True
    return _docker_sigkill(exc)


def resource_error_from_text(
    text: str,
    *,
    app: Optional[str] = None,
    image: Optional[str] = None,
    action: str = "",
) -> Optional[OperatorError]:
    """Map a failure blob to an OOM/disk OperatorError when it matches."""
    if looks_like_host_oom(text):
        return OperatorError(
            host_oom_message(detail=text, app=app, image=image, action=action)
        )
    if looks_like_disk_full(text):
        return OperatorError(
            disk_full_message(detail=text, app=app, image=image, action=action)
        )
    return None


def resource_error_from_exc(
    exc: BaseException,
    *,
    app: Optional[str] = None,
    image: Optional[str] = None,
    action: str = "",
) -> Optional[OperatorError]:
    detail = subprocess_detail(exc) if isinstance(exc, subprocess.CalledProcessError) else str(exc)
    blob = _resource_blob(exc)
    if looks_like_host_oom_exc(exc):
        return OperatorError(
            host_oom_message(detail=detail or blob, app=app, image=image, action=action)
        )
    if looks_like_disk_full(blob):
        return OperatorError(
            disk_full_message(detail=detail or blob, app=app, image=image, action=action)
        )
    return None


def host_oom_message(
    *,
    detail: str = "",
    app: Optional[str] = None,
    image: Optional[str] = None,
    action: str = "",
) -> str:
    return format_cta(
        _resource_headline("insufficient host memory (OOM)", app=app, image=image, action=action),
        (
            "free memory on this VPS (stop unused containers or processes)",
            "raise host RAM or App/container memory limits if the workload needs more",
            _retry_step(app=app),
            "raft doctor",
        ),
        detail=detail,
        tag="docker",
        preamble=(
            "This is a host capacity problem — not registry auth, credentials,"
            " or a bad image manifest.",
        ),
    )


def disk_full_message(
    *,
    detail: str = "",
    app: Optional[str] = None,
    image: Optional[str] = None,
    action: str = "",
) -> str:
    return format_cta(
        _resource_headline("insufficient host disk space", app=app, image=image, action=action),
        (
            "free disk on this VPS (logs, unused images, old layers)",
            "docker system df   # see what Docker is using",
            _retry_step(app=app),
            "raft doctor",
        ),
        detail=detail,
        tag="docker",
        preamble=(
            "This is a host disk space problem — not registry auth, credentials,"
            " or a bad image manifest.",
        ),
    )


def _resource_headline(
    kind: str,
    *,
    app: Optional[str],
    image: Optional[str],
    action: str,
) -> str:
    target = _resource_target(app=app, image=image)
    if target and action:
        return f"{target} failed while trying to {action}: {kind}."
    if target:
        return f"{target}: {kind}."
    if action:
        return f"docker failed while trying to {action}: {kind}."
    return f"docker operation failed: {kind}."


def _resource_target(*, app: Optional[str], image: Optional[str]) -> str:
    if app and image:
        return f"App {app!r} ({image})"
    if app:
        return f"App {app!r}"
    if image:
        return f"image {image!r}"
    return ""


def _retry_step(*, app: Optional[str]) -> str:
    if app:
        return f"retry: raft sync {app}   # or re-run: raft apply …"
    return "retry: raft apply …   # or: raft sync <app> / raft redeploy <app>"


def _resource_blob(exc: BaseException) -> str:
    parts = [exc_blob(exc)]
    if isinstance(exc, subprocess.CalledProcessError):
        parts.append(subprocess_detail(exc).lower())
    return " ".join(parts)


def _docker_sigkill(exc: BaseException) -> bool:
    if not isinstance(exc, subprocess.CalledProcessError):
        return False
    if exc.returncode != 137:
        return False
    cmd = " ".join(str(p) for p in (exc.cmd or [])).lower()
    return "docker" in cmd
