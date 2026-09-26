"""Helpers for asserting OperatorError / CTA shape without locking to prose."""

from __future__ import annotations

import logging
from typing import Optional, Sequence, Union

from raft.errors import OperatorError


def assert_operator(
    exc: BaseException,
    *,
    has_fix: Optional[bool] = True,
    contains: Sequence[str] = (),
    fix_label: str = "Fix:",
) -> None:
    """Assert ``exc`` is OperatorError with optional Fix marker and tokens."""
    assert isinstance(exc, OperatorError)
    if has_fix is not None:
        assert exc.has_fix is has_fix
    text = str(exc)
    if has_fix:
        assert fix_label in text
    for token in contains:
        assert token in text, f"missing {token!r} in {text!r}"


def assert_cta(
    message: str,
    *,
    contains: Sequence[str] = (),
    fix_label: str = "Fix:",
    tag: str = "",
) -> None:
    """Assert a format_cta-built message has Fix structure and stable tokens."""
    assert fix_label in message
    assert "  1. " in message
    for token in contains:
        assert token in message, f"missing {token!r} in {message!r}"
    if tag:
        assert f"({tag}:" in message


def assert_logged(
    caplog,
    *,
    level: Union[int, str] = logging.INFO,
    contains: Sequence[str] = (),
    count_at_least: int = 1,
) -> None:
    """Assert at least one log record at ``level`` includes all ``contains`` tokens."""
    if isinstance(level, str):
        level = getattr(logging, level.upper())
    matches = [
        r
        for r in caplog.records
        if r.levelno == level and all(t in r.getMessage() for t in contains)
    ]
    assert len(matches) >= count_at_least, (
        f"expected ≥{count_at_least} {logging.getLevelName(level)} log(s) "
        f"containing {list(contains)!r}; got {[r.getMessage() for r in caplog.records]!r}"
    )
