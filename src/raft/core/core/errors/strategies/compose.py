"""Classify docker compose failures."""

import subprocess

from ..classify_ctx import SubprocessCtx
from ..cmd_parts import CmdParts
from ..docker_msgs import DockerMessages
from ..operator_error import OperatorError
from .rule import SubprocessRule


class ComposeRule(SubprocessRule):
    name = "compose"

    def match(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> bool:
        del ctx, detail
        parts = CmdParts.parts(exc)
        return "docker" in parts and "compose" in parts

    def build(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> OperatorError:
        del exc
        action = ctx.action or "run docker compose"
        return OperatorError(DockerMessages.compose_failure_message(action, detail=detail))
