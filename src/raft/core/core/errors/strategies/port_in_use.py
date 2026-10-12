"""Classify published-port-in-use failures."""

import subprocess

from ..classify_ctx import SubprocessCtx
from ..docker_msgs import DockerMessages
from ..operator_error import OperatorError
from .rule import SubprocessRule


class PortInUseRule(SubprocessRule):
    name = "port_in_use"

    def match(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> bool:
        del ctx, detail
        return DockerMessages.looks_like_port_in_use(exc)

    def build(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> OperatorError:
        del exc, ctx
        return OperatorError(DockerMessages.port_in_use_message(detail=detail))
