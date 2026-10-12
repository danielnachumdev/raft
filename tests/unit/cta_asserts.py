"""Helpers for asserting OperatorError / CTA shape without locking to prose."""

import logging
from contextlib import contextmanager
from typing import Iterator, Optional, Sequence, Union

import pytest

from raft.errors.cta import OperatorError


class CtaAsserts:
    @classmethod
    def operator(
        cls,
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

    @classmethod
    def cta(
        cls,
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

    @classmethod
    def logged(
        cls,
        caplog,
        *,
        level: Union[int, str] = logging.INFO,
        contains: Sequence[str] = (),
        count_at_least: int = 1,
    ) -> None:
        """Assert at least one log record at ``level`` includes all ``contains``."""
        if isinstance(level, str):
            level = getattr(logging, level.upper())
        matches = [
            r
            for r in caplog.records
            if r.levelno == level and all(t in r.getMessage() for t in contains)
        ]
        assert len(matches) >= count_at_least, (
            f"expected ≥{count_at_least} {logging.getLevelName(level)} log(s) "
            f"containing {list(contains)!r}; got "
            f"{[r.getMessage() for r in caplog.records]!r}"
        )

    @classmethod
    @contextmanager
    def raises(
        cls,
        *,
        match: Optional[str] = None,
        has_fix: Optional[bool] = True,
        contains: Sequence[str] = (),
    ) -> Iterator[pytest.ExceptionInfo]:
        """``pytest.raises(OperatorError)`` then ``operator`` on the exception."""
        kwargs = {}
        if match is not None:
            kwargs["match"] = match
        with pytest.raises(OperatorError, **kwargs) as caught:
            yield caught
        cls.operator(caught.value, has_fix=has_fix, contains=contains)
