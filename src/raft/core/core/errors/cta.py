"""Operator CTA primitives: ``OperatorError`` and ``CtaFormatter``."""

import subprocess
from typing import Sequence

from .operator_error import OperatorError

__all__ = [
    "CtaFormatter",
    "OperatorError",
    "exc_blob",
    "format_cta",
    "operator",
    "subprocess_detail",
]


class CtaFormatter:
    """Build stable operator messages with numbered Fix steps."""

    @staticmethod
    def first_line(detail: str) -> str:
        stripped = detail.strip()
        if not stripped:
            return ""
        return stripped.splitlines()[0].strip()

    @staticmethod
    def subprocess_detail(exc: BaseException) -> str:
        if isinstance(exc, subprocess.CalledProcessError):
            return (exc.stderr or exc.output or "").strip()
        return str(exc).strip()

    @staticmethod
    def exc_blob(exc: BaseException) -> str:
        text = str(exc).lower()
        if isinstance(exc, subprocess.CalledProcessError):
            text = f"{text} {(exc.stderr or '')} {(exc.output or '')}".lower()
        return text

    @classmethod
    def format(
        cls,
        headline: str,
        steps: Sequence[str],
        *,
        detail: str = "",
        tag: str = "",
        hint: str = "",
        fix_label: str = "Fix:",
        preamble: Sequence[str] = (),
    ) -> str:
        lines: list[str] = [headline, *preamble, "", fix_label]
        if hint:
            lines.append(f"  hint: {hint}")
        for index, step in enumerate(steps, start=1):
            lines.append(f"  {index}. {step}")
        first = cls.first_line(detail)
        if first and tag:
            lines.extend(["", f"({tag}: {first})"])
        elif first:
            lines.extend(["", first])
        return "\n".join(lines)

    @classmethod
    def operator(
        cls,
        headline: str,
        steps: Sequence[str],
        *,
        detail: str = "",
        tag: str = "",
        hint: str = "",
        fix_label: str = "Fix:",
        preamble: Sequence[str] = (),
    ) -> OperatorError:
        return OperatorError(
            cls.format(
                headline,
                steps,
                detail=detail,
                tag=tag,
                hint=hint,
                fix_label=fix_label,
                preamble=preamble,
            )
        )


exc_blob = CtaFormatter.exc_blob
format_cta = CtaFormatter.format
operator = CtaFormatter.operator
subprocess_detail = CtaFormatter.subprocess_detail
