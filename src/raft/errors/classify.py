"""Declarative subprocess failure classification."""

import subprocess
from typing import Optional, Sequence

from .classify_ctx import SubprocessCtx
from .cmd_parts import CmdParts
from .cta import CtaFormatter
from .operator_error import OperatorError
from .strategies import SUBPROCESS_STRATEGIES, SubprocessRule

__all__ = ["SubprocessClassifier", "SubprocessCtx"]


class SubprocessClassifier:
    """Match ``CalledProcessError`` against registered subprocess strategies."""

    def __init__(self, rules: Optional[Sequence[SubprocessRule]] = None) -> None:
        self._rules = tuple(rules) if rules is not None else SUBPROCESS_STRATEGIES

    def classify(
        self,
        exc: subprocess.CalledProcessError,
        ctx: Optional[SubprocessCtx] = None,
    ) -> Optional[OperatorError]:
        """Return an OperatorError when ``exc`` matches a known failure class."""
        context = ctx or SubprocessCtx()
        detail = CtaFormatter.subprocess_detail(exc)
        for rule in self._rules:
            if rule.match(exc, context, detail):
                return rule.build(exc, context, detail)
        return None

    @staticmethod
    def generic_command_failed(exc: subprocess.CalledProcessError) -> OperatorError:
        detail = CtaFormatter.subprocess_detail(exc)
        cmd = CmdParts.text(exc)
        lines = [f"command failed ({exc.returncode}): {cmd}"]
        if detail:
            lines.append(detail)
        return OperatorError("\n".join(lines), has_fix=False)
