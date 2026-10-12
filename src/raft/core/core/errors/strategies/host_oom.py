"""Classify host OOM failures."""

import subprocess

from ..classify_ctx import SubprocessCtx
from ..cmd_parts import CmdParts
from ..operator_error import OperatorError
from ..resource_msgs import ResourceMessages
from .rule import SubprocessRule


class HostOomRule(SubprocessRule):
    name = "host_oom"

    def match(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> bool:
        del ctx
        return ResourceMessages.looks_like_host_oom_exc(exc) or ResourceMessages.looks_like_host_oom(
            detail
        )

    def build(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> OperatorError:
        image = CmdParts.pull_image(exc)
        action = ctx.action or ("pull image" if image else "")
        return ResourceMessages.from_subprocess(
            exc, app=ctx.app, image=image, action=action, detail=detail
        )
