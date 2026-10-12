"""Classify private registry unauthorized pull failures."""

import subprocess

from ..classify_ctx import SubprocessCtx
from ..cmd_parts import CmdParts
from ..operator_error import OperatorError
from ..registry_msgs import RegistryMessages
from .rule import SubprocessRule


class RegistryPullRule(SubprocessRule):
    name = "registry_pull"

    def match(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> bool:
        del ctx
        cmd = CmdParts.text(exc)
        return (
            "docker" in cmd
            and "pull" in cmd
            and RegistryMessages.looks_like_registry_unauthorized(CmdParts.blob(exc, detail))
        )

    def build(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> OperatorError:
        parts = CmdParts.parts(exc)
        image = parts[-1] if parts else "image"
        return OperatorError(
            RegistryMessages.registry_unauthorized_message(
                image, detail=detail, app=ctx.app, repo=ctx.repo
            )
        )
