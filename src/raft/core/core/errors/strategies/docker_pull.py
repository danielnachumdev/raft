"""Classify generic docker pull failures."""

import subprocess

from ..classify_ctx import SubprocessCtx
from ..cmd_parts import CmdParts
from ..docker_msgs import DockerMessages
from ..operator_error import OperatorError
from .rule import SubprocessRule


class DockerPullRule(SubprocessRule):
    name = "docker_pull"

    def match(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> bool:
        del ctx, detail
        cmd = CmdParts.text(exc)
        return "docker" in cmd and "pull" in cmd

    def build(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> OperatorError:
        parts = CmdParts.parts(exc)
        image = parts[-1] if parts else "image"
        return OperatorError(
            DockerMessages.docker_pull_failure_message(image, detail=detail, app=ctx.app)
        )
