"""Checked runners that raise OperatorError via classification."""

import subprocess
from typing import Any, Optional, Sequence

from .classify_ctx import SubprocessCtx
from .cta import CtaFormatter
from .docker_msgs import DockerMessages
from .git_msgs import GitMessages
from .operator_error import OperatorError
from .registry_msgs import RegistryMessages
from .resource_msgs import ResourceMessages

__all__ = ["CheckedCommands"]


class CheckedCommands:
    """Raise OperatorError for known compose / docker / git failure classes."""

    @staticmethod
    def raise_for_compose_failure(
        exc: BaseException,
        *,
        action: str,
        hint: str = "",
        app: Optional[str] = None,
        image: Optional[str] = None,
    ) -> None:
        detail = (
            CtaFormatter.subprocess_detail(exc)
            if isinstance(exc, subprocess.CalledProcessError)
            else str(exc)
        )
        resource = ResourceMessages.resource_error_from_exc(
            exc, app=app, image=image, action=action
        )
        if resource is not None:
            raise resource from exc
        if DockerMessages.looks_like_docker_daemon_down(exc):
            raise OperatorError(DockerMessages.docker_daemon_message(detail=detail)) from exc
        if DockerMessages.looks_like_port_in_use(exc):
            raise OperatorError(DockerMessages.port_in_use_message(detail=detail)) from exc
        raise OperatorError(
            DockerMessages.compose_failure_message(action, detail=detail, hint=hint)
        ) from exc

    @classmethod
    def raise_for_docker_pull_failure(
        cls,
        image: str,
        *,
        detail: str = "",
        app: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> None:
        """Always raise OperatorError for a failed ``docker pull``."""
        resource = ResourceMessages.resource_error_from_text(
            detail, app=app, image=image, action="pull image"
        )
        if resource is not None:
            raise resource
        if RegistryMessages.looks_like_registry_unauthorized(detail):
            raise OperatorError(
                RegistryMessages.registry_unauthorized_message(
                    image, detail=detail, app=app, repo=repo
                )
            )
        cls._raise_daemon_or_pull(image, detail=detail, app=app)

    @staticmethod
    def _raise_daemon_or_pull(
        image: str, *, detail: str, app: Optional[str]
    ) -> None:
        blob = detail.lower()
        if (
            DockerMessages.looks_like_docker_daemon_down(
                subprocess.CalledProcessError(1, ["docker", "pull"], stderr=detail)
            )
            or "cannot connect to the docker daemon" in blob
        ):
            raise OperatorError(DockerMessages.docker_daemon_message(detail=detail))
        raise OperatorError(
            DockerMessages.docker_pull_failure_message(image, detail=detail, app=app)
        )

    @staticmethod
    def raise_for_git_failure(
        exc: BaseException,
        repo: str,
        *,
        app: Optional[str] = None,
        always: bool = False,
    ) -> None:
        """Re-raise ``exc`` as OperatorError for known git classes."""
        detail = (
            CtaFormatter.subprocess_detail(exc)
            if isinstance(exc, subprocess.CalledProcessError)
            else ""
        )
        if not detail and not isinstance(exc, subprocess.CalledProcessError):
            detail = str(exc)
        if GitMessages.looks_like_git_auth_failure(exc):
            raise OperatorError(
                GitMessages.git_auth_failure_message(repo, app=app, detail=detail)
            ) from exc
        if GitMessages.looks_like_git_network_failure(exc):
            raise OperatorError(
                GitMessages.git_network_failure_message(repo, detail=detail)
            ) from exc
        if always:
            raise OperatorError(
                GitMessages.git_generic_failure_message(repo, app=app, detail=detail)
            ) from exc

    @classmethod
    def run_compose(
        cls,
        shell: Any,
        args: Sequence[str],
        *,
        action: str,
        hint: str = "",
        stream: bool = False,
    ):
        """Run ``docker compose *args``; raise OperatorError on failure."""
        result = shell.compose(*args, capture=not stream, check=False)
        if result.returncode == 0:
            return result
        cls._raise_compose_failure(result, args, action=action, hint=hint, stream=stream)
        return result  # pragma: no cover

    @classmethod
    def _raise_compose_failure(
        cls,
        result: Any,
        args: Sequence[str],
        *,
        action: str,
        hint: str,
        stream: bool,
    ) -> None:
        if stream:
            raise OperatorError(
                DockerMessages.compose_failure_message(
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
        cls.raise_for_compose_failure(exc, action=action, hint=hint)

    @classmethod
    def run_docker(
        cls,
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
        if DockerMessages.looks_like_docker_daemon_down(exc):
            raise OperatorError(DockerMessages.docker_daemon_message(detail=detail)) from exc
        image = str(args[-1]) if args else None
        resource = ResourceMessages.resource_error_from_exc(exc, image=image, action=action)
        if resource is not None:
            raise resource from exc
        raise OperatorError(
            DockerMessages.docker_failure_message(action, detail=detail, hint=hint)
        ) from exc

    @classmethod
    def run(
        cls,
        runner: Any,
        args: Sequence[str],
        *,
        kind: str,
        action: str,
        hint: str = "",
        ctx: Optional[SubprocessCtx] = None,
    ):
        """Dispatch to compose/docker checked runners by ``kind``."""
        del ctx  # reserved for future classify wiring
        if kind == "compose":
            return cls.run_compose(runner, args, action=action, hint=hint)
        if kind == "docker":
            return cls.run_docker(runner, args, action=action, hint=hint)
        raise ValueError(f"unsupported run_checked kind: {kind!r}")
