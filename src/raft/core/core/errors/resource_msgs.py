"""Host resource exhaustion CTAs (OOM / disk) for Docker apply paths."""

import subprocess
from typing import Optional

from .cta import CtaFormatter
from .operator_error import OperatorError

__all__ = ["ResourceMessages"]

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


class ResourceMessages:
    """Host OOM / disk-full classifiers and CTA builders."""

    @staticmethod
    def looks_like_host_oom(text: str) -> bool:
        lower = (text or "").lower()
        return any(marker in lower for marker in _OOM_MARKERS)

    @staticmethod
    def looks_like_disk_full(text: str) -> bool:
        lower = (text or "").lower()
        return any(marker in lower for marker in _DISK_MARKERS)

    @classmethod
    def looks_like_host_oom_exc(cls, exc: BaseException) -> bool:
        if cls.looks_like_host_oom(cls._blob(exc)):
            return True
        return cls._docker_sigkill(exc)

    @classmethod
    def resource_error_from_text(
        cls,
        text: str,
        *,
        app: Optional[str] = None,
        image: Optional[str] = None,
        action: str = "",
    ) -> Optional[OperatorError]:
        """Map a failure blob to an OOM/disk OperatorError when it matches."""
        if cls.looks_like_host_oom(text):
            return OperatorError(
                cls.host_oom_message(detail=text, app=app, image=image, action=action)
            )
        if cls.looks_like_disk_full(text):
            return OperatorError(
                cls.disk_full_message(detail=text, app=app, image=image, action=action)
            )
        return None

    @classmethod
    def resource_error_from_exc(
        cls,
        exc: BaseException,
        *,
        app: Optional[str] = None,
        image: Optional[str] = None,
        action: str = "",
    ) -> Optional[OperatorError]:
        detail = (
            CtaFormatter.subprocess_detail(exc)
            if isinstance(exc, subprocess.CalledProcessError)
            else str(exc)
        )
        blob = cls._blob(exc)
        if cls.looks_like_host_oom_exc(exc):
            return OperatorError(
                cls.host_oom_message(detail=detail or blob, app=app, image=image, action=action)
            )
        if cls.looks_like_disk_full(blob):
            return OperatorError(
                cls.disk_full_message(detail=detail or blob, app=app, image=image, action=action)
            )
        return None

    @classmethod
    def from_subprocess(
        cls,
        exc: subprocess.CalledProcessError,
        *,
        app: Optional[str] = None,
        image: Optional[str] = None,
        action: str = "",
        detail: str = "",
    ) -> OperatorError:
        """Best-effort resource error; fall back to host OOM CTA."""
        err = cls.resource_error_from_text(detail, app=app, image=image, action=action)
        if err is not None:
            return err
        return cls.resource_error_from_exc(
            exc, app=app, image=image, action=action
        ) or OperatorError(
            cls.host_oom_message(detail=detail, app=app, image=image, action=action)
        )

    @classmethod
    def host_oom_message(
        cls,
        *,
        detail: str = "",
        app: Optional[str] = None,
        image: Optional[str] = None,
        action: str = "",
    ) -> str:
        return CtaFormatter.format(
            cls._headline("insufficient host memory (OOM)", app=app, image=image, action=action),
            (
                "free memory on this VPS (stop unused containers or processes)",
                "raise host RAM or App/container memory limits if the workload needs more",
                cls._retry_step(app=app),
                "raft doctor",
            ),
            detail=detail,
            tag="docker",
            preamble=(
                "This is a host capacity problem — not registry auth, credentials,"
                " or a bad image manifest.",
            ),
        )

    @classmethod
    def disk_full_message(
        cls,
        *,
        detail: str = "",
        app: Optional[str] = None,
        image: Optional[str] = None,
        action: str = "",
    ) -> str:
        return CtaFormatter.format(
            cls._headline("insufficient host disk space", app=app, image=image, action=action),
            (
                "free disk on this VPS (logs, unused images, old layers)",
                "docker system df   # see what Docker is using",
                cls._retry_step(app=app),
                "raft doctor",
            ),
            detail=detail,
            tag="docker",
            preamble=(
                "This is a host disk space problem — not registry auth, credentials,"
                " or a bad image manifest.",
            ),
        )

    @classmethod
    def _headline(
        cls,
        kind: str,
        *,
        app: Optional[str],
        image: Optional[str],
        action: str,
    ) -> str:
        target = cls._target(app=app, image=image)
        if target and action:
            return f"{target} failed while trying to {action}: {kind}."
        if target:
            return f"{target}: {kind}."
        if action:
            return f"docker failed while trying to {action}: {kind}."
        return f"docker operation failed: {kind}."

    @staticmethod
    def _target(*, app: Optional[str], image: Optional[str]) -> str:
        if app and image:
            return f"App {app!r} ({image})"
        if app:
            return f"App {app!r}"
        if image:
            return f"image {image!r}"
        return ""

    @staticmethod
    def _retry_step(*, app: Optional[str]) -> str:
        if app:
            return f"retry: raft sync {app}   # or re-run: raft apply …"
        return "retry: raft apply …   # or: raft sync <app> / raft redeploy <app>"

    @staticmethod
    def _blob(exc: BaseException) -> str:
        parts = [CtaFormatter.exc_blob(exc)]
        if isinstance(exc, subprocess.CalledProcessError):
            parts.append(CtaFormatter.subprocess_detail(exc).lower())
        return " ".join(parts)

    @staticmethod
    def _docker_sigkill(exc: BaseException) -> bool:
        if not isinstance(exc, subprocess.CalledProcessError):
            return False
        if exc.returncode != 137:
            return False
        cmd = " ".join(str(p) for p in (exc.cmd or [])).lower()
        return "docker" in cmd
