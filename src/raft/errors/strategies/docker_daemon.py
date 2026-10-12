"""Classify Docker daemon-down failures."""

import subprocess

from ..classify_ctx import SubprocessCtx
from ..docker_msgs import DockerMessages
from ..operator_error import OperatorError
from .rule import SubprocessRule


class DockerDaemonRule(SubprocessRule):
    name = "docker_daemon"

    def match(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> bool:
        del ctx, detail
        return DockerMessages.looks_like_docker_daemon_down(exc)

    def build(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> OperatorError:
        del exc, ctx
        return OperatorError(DockerMessages.docker_daemon_message(detail=detail))
