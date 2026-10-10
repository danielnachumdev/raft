"""Inject the active TraceContext id onto log records."""

from __future__ import annotations

import logging

from ..trace import TraceContext


class TraceIdFilter(logging.Filter):
    """Inject ``record.tid`` from the active :class:`TraceContext` (or ``-``)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.tid = TraceContext.current() or "-"  # type: ignore[attr-defined]
        return True
