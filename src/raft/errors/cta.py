"""Operator CTA primitives: ``OperatorError`` and ``format_cta``.

Add a Rule in ``classify`` or a factory in ``domain`` — do not hand-build Fix strings.
"""

from __future__ import annotations

import subprocess
from typing import Optional, Sequence


class OperatorError(RuntimeError):
    """Operator-facing failure that already includes a Fix CTA."""

    def __init__(self, message: str, *, has_fix: bool = True) -> None:
        super().__init__(message)
        self.has_fix = has_fix


def first_line(detail: str) -> str:
    stripped = detail.strip()
    if not stripped:
        return ""
    return stripped.splitlines()[0].strip()


def subprocess_detail(exc: BaseException) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        return (exc.stderr or exc.output or "").strip()
    return str(exc).strip()


def exc_blob(exc: BaseException) -> str:
    text = str(exc).lower()
    if isinstance(exc, subprocess.CalledProcessError):
        text = f"{text} {(exc.stderr or '')} {(exc.output or '')}".lower()
    return text


def format_cta(
    headline: str,
    steps: Sequence[str],
    *,
    detail: str = "",
    tag: str = "",
    hint: str = "",
    fix_label: str = "Fix:",
    preamble: Sequence[str] = (),
) -> str:
    """Build a stable operator message with numbered Fix steps."""
    lines: list[str] = [headline]
    for line in preamble:
        lines.append(line)
    lines.append("")
    lines.append(fix_label)
    if hint:
        lines.append(f"  hint: {hint}")
    for index, step in enumerate(steps, start=1):
        lines.append(f"  {index}. {step}")
    first = first_line(detail)
    if first and tag:
        lines.extend(["", f"({tag}: {first})"])
    elif first:
        lines.extend(["", first])
    return "\n".join(lines)


def operator(
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
        format_cta(
            headline,
            steps,
            detail=detail,
            tag=tag,
            hint=hint,
            fix_label=fix_label,
            preamble=preamble,
        )
    )
