"""Classify git subprocess failures."""

import subprocess

from ..classify_ctx import SubprocessCtx
from ..cmd_parts import CmdParts
from ..git_msgs import GitMessages
from ..operator_error import OperatorError
from .rule import SubprocessRule


class GitRule(SubprocessRule):
    name = "git"

    def match(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> bool:
        del ctx, detail
        parts = CmdParts.parts(exc)
        return bool(parts) and parts[0] == "git"

    def build(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> OperatorError:
        parts = CmdParts.parts(exc)
        repo = ctx.repo or next(
            (a for a in reversed(parts) if ":" in a or a.endswith(".git")),
            "<repo>",
        )
        if GitMessages.looks_like_git_auth_failure(exc):
            return OperatorError(
                GitMessages.git_auth_failure_message(repo, app=ctx.app, detail=detail)
            )
        if GitMessages.looks_like_git_network_failure(exc):
            return OperatorError(GitMessages.git_network_failure_message(repo, detail=detail))
        return OperatorError(
            GitMessages.git_generic_failure_message(repo, app=ctx.app, detail=detail)
        )
